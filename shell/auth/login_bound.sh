#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=runtime.sh
source "$SCRIPT_DIR/runtime.sh"
AUTH_PYTHON="$(shell_auth_python)"
# shellcheck source=../common/env.sh
source "$SCRIPT_DIR/../common/env.sh"
# shellcheck source=../common/response.sh
source "$SCRIPT_DIR/../common/response.sh"
# shellcheck source=../common/log.sh
source "$SCRIPT_DIR/../common/log.sh"
# shellcheck source=../common/db.sh
source "$SCRIPT_DIR/../common/db.sh"
# shellcheck source=../common/cookie.sh
source "$SCRIPT_DIR/../common/cookie.sh"

user_id="${1:-}"
if [[ -z "$user_id" ]]; then
  shell_response_json false "user_id is required" null
  exit 1
fi

shell_db_init
shell_env_ensure_user_runtime_dir "$user_id" >/dev/null

bound_account_json="$(shell_db_query "SELECT user_id, campus_account FROM campus_accounts WHERE user_id = ?" "$user_id")"
if [[ "$bound_account_json" == "[]" ]]; then
  shell_log_write ERROR auth "webvpn login failed: campus account not bound" "user_id=$user_id" "$user_id"
  shell_response_json false "campus account is not bound" null
  exit 1
fi

if ! result_json="$("$AUTH_PYTHON" "$SCRIPT_DIR/webvpn_client.py" login "$user_id" 2>&1)"; then
  shell_log_write ERROR auth "webvpn login failed" "user_id=$user_id result=$result_json" "$user_id"
  printf '%s\n' "$result_json"
  exit 1
fi

campus_account="$(python - "$bound_account_json" <<'PY'
import json, sys
rows = json.loads(sys.argv[1])
print(rows[0]["campus_account"] if rows else "")
PY
)"

shell_log_write INFO auth "webvpn login completed" "user_id=$user_id account=$campus_account" "$user_id"
printf '%s\n' "$result_json"
