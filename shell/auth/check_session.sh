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

if ! result_json="$("$AUTH_PYTHON" "$SCRIPT_DIR/webvpn_client.py" check "$user_id" 2>&1)"; then
  shell_log_write WARNING auth "webvpn session invalid" "user_id=$user_id result=$result_json" "$user_id"
  if [[ -z "$result_json" || "$result_json" != *'"success"'* ]]; then
    result_json="$(shell_response_json false "session check failed" null)"
  fi
  printf '%s\n' "$result_json"
  exit 1
fi

cookie_file="$(shell_cookie_path "$user_id")"
shell_db_execute "UPDATE campus_accounts SET session_valid=1, last_login_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE user_id=?" "$user_id" 2>/dev/null || true
shell_log_write INFO auth "webvpn session checked" "user_id=$user_id cookie=$cookie_file" "$user_id"
printf '%s\n' "$result_json"
