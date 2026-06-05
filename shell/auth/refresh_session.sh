#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/runtime.sh"
AUTH_PYTHON="$(shell_auth_python)"
source "$SCRIPT_DIR/../common/env.sh"
source "$SCRIPT_DIR/../common/response.sh"
source "$SCRIPT_DIR/../common/log.sh"
source "$SCRIPT_DIR/../common/db.sh"

user_id="${1:-}"
if [[ -z "$user_id" ]]; then
  shell_response_json false "user_id is required" null
  exit 1
fi

shell_db_init

bound_account_json="$(shell_db_query "SELECT user_id FROM campus_accounts WHERE user_id = ?" "$user_id")"
if [[ "$bound_account_json" == "[]" ]]; then
  shell_log_write ERROR auth "refresh failed: campus account missing" "user_id=$user_id" "$user_id"
  shell_response_json false "campus account is not bound" null
  exit 1
fi

check_result="$("$AUTH_PYTHON" "$SCRIPT_DIR/webvpn_client.py" check "$user_id" 2>&1 || true)"
if [[ "$check_result" == *'"success": true'* || "$check_result" == *'"success":true'* ]]; then
  shell_db_execute "UPDATE campus_accounts SET session_valid = 1, last_login_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?" "$user_id"
  shell_log_write INFO auth "webvpn session still valid" "user_id=$user_id" "$user_id"
  printf '%s\n' "$check_result"
  exit 0
fi

shell_log_write WARNING auth "webvpn session expired, attempting silent relogin" "user_id=$user_id" "$user_id"

login_result="$("$AUTH_PYTHON" "$SCRIPT_DIR/webvpn_client.py" login "$user_id" 2>&1 || true)"
if [[ "$login_result" == *'"success": true'* || "$login_result" == *'"success":true'* ]]; then
  shell_log_write INFO auth "webvpn session refreshed by silent relogin" "user_id=$user_id" "$user_id"
  printf '%s\n' "$login_result"
  exit 0
fi

shell_log_write WARNING auth "webvpn session refresh failed; interactive login required" "user_id=$user_id" "$user_id"
shell_response_json false "WebVPN session has expired. Please run bind_webvpn_interactive.sh to re-login." \
  '{"action": "interactive_login_required", "command": "bind_webvpn_interactive.sh"}'
exit 1
