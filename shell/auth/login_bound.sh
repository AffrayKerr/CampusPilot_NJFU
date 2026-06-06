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

user_id="${1:-}"
if [[ -z "$user_id" ]]; then
  shell_response_json false "user_id is required" null
  exit 1
fi

shell_db_init
shell_env_ensure_user_runtime_dir "$user_id" >/dev/null

bound_account_json="$(shell_db_query "SELECT user_id, campus_account FROM campus_accounts WHERE user_id = ?" "$user_id")"
if [[ "$bound_account_json" == "[]" ]]; then
  shell_log_write ERROR auth "login failed: campus account not bound" "user_id=$user_id" "$user_id"
  shell_response_json false "campus account is not bound" null
  exit 1
fi

# Check if a valid cookie file already exists
check_result="$("$AUTH_PYTHON" "$SCRIPT_DIR/webvpn_client.py" check "$user_id" 2>&1 || true)"
if [[ "$check_result" == *'"success": true'* || "$check_result" == *'"success":true'* ]]; then
  shell_log_write INFO auth "webvpn session already valid" "user_id=$user_id" "$user_id"
  printf '%s\n' "$check_result"
  exit 0
fi

# Session is invalid or no cookie file — interactive login required
shell_log_write WARNING auth "webvpn session invalid, interactive login required" "user_id=$user_id" "$user_id"
shell_response_json false "WebVPN session is not active. Please run bind_webvpn_interactive.sh to login via browser." \
  '{"action": "run_interactive_login", "command": "bind_webvpn_interactive.sh"}'
exit 1
