#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../auth/runtime.sh
source "$SCRIPT_DIR/../auth/runtime.sh"
AUTH_PYTHON="$(shell_auth_python)"
# shellcheck source=../common/env.sh
source "$SCRIPT_DIR/../common/env.sh"
# shellcheck source=../common/response.sh
source "$SCRIPT_DIR/../common/response.sh"
# shellcheck source=../common/log.sh
source "$SCRIPT_DIR/../common/log.sh"
# shellcheck source=../common/db.sh
source "$SCRIPT_DIR/../common/db.sh"

user_id="${1:-}"
sync_interval_days="${2:-7}"

if [[ -z "$user_id" ]]; then
  shell_response_json false "user_id is required" null
  exit 1
fi

shell_db_init

bound_account_json="$(shell_db_query "SELECT user_id FROM campus_accounts WHERE user_id = ?" "$user_id")"
if [[ "$bound_account_json" == "[]" ]]; then
  shell_log_write WARNING schedule "auto sync skipped: campus account not bound" "user_id=$user_id" "$user_id"
  shell_response_json false "campus account is not bound" null
  exit 1
fi

last_sync_json="$(shell_db_query "SELECT MAX(updated_at) as last_sync FROM schedules WHERE user_id = ?" "$user_id")"
last_sync="$(echo "$last_sync_json" | "$AUTH_PYTHON" -c "import json, sys; d = json.load(sys.stdin); print(d[0]['last_sync'] if d and d[0]['last_sync'] else '')")"

should_sync="$("$AUTH_PYTHON" - "$last_sync" "$sync_interval_days" <<'PY'
import sys
from datetime import datetime, timedelta

last_sync_str = sys.argv[1]
interval_days = int(sys.argv[2])

if not last_sync_str:
    print("true")
    sys.exit(0)

try:
    last_sync = datetime.fromisoformat(last_sync_str.replace(' ', 'T'))
    now = datetime.now()
    delta = now - last_sync
    
    if delta.total_seconds() / 86400 >= interval_days:
        print("true")
    else:
        print("false")
except Exception:
    print("true")
PY
)"

if [[ "$should_sync" != "true" ]]; then
  shell_log_write INFO schedule "auto sync skipped: within sync interval" "user_id=$user_id last_sync=$last_sync" "$user_id"
  shell_response_json true "Schedule is up to date" "{\"last_sync\": \"$last_sync\", \"sync_interval_days\": $sync_interval_days}"
  exit 0
fi

shell_log_write INFO schedule "auto sync triggered" "user_id=$user_id last_sync=$last_sync interval_days=$sync_interval_days" "$user_id"

if ! sync_result="$(bash "$SCRIPT_DIR/sync_schedule.sh" "$user_id" 2>&1)"; then
  shell_log_write ERROR schedule "auto sync failed" "user_id=$user_id result=$sync_result" "$user_id"
  shell_response_json false "Auto sync failed" "{\"last_sync\": \"$last_sync\"}"
  exit 1
fi

shell_log_write INFO schedule "auto sync completed" "user_id=$user_id" "$user_id"

result_data="$(echo "$sync_result" | "$AUTH_PYTHON" -c "import json, sys; d = json.loads(sys.stdin.read()); print(json.dumps(d.get('data', {})))")"
shell_response_json true "Auto sync completed" "$result_data"
