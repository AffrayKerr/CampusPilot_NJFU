#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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

campus_account="${1:-}"
campus_password="${2:-}"
email="${3:-}"
user_id="${4:-}"

if [[ -z "$campus_account" || -z "$campus_password" || -z "$user_id" ]]; then
  shell_response_json false "campus_account, campus_password and user_id are required" null
  exit 1
fi

shell_db_init
shell_env_ensure_user_runtime_dir "$user_id" >/dev/null

bound_account_json="$(shell_db_query "SELECT user_id, campus_account FROM campus_accounts WHERE user_id = ?" "$user_id")"
if [[ "$bound_account_json" == "[]" ]]; then
  shell_response_json false "campus account is not bound" null
  exit 1
fi

cookie_content="webvpn_session=${user_id}_$(date +%s)"
cookie_file="$(shell_cookie_save "$user_id" "$cookie_content")"

shell_db_execute "UPDATE campus_accounts SET webvpn_cookie_path = ?, session_valid = 1, last_login_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?" "$cookie_file" "$user_id"
shell_db_execute "INSERT INTO sessions (user_id, session_type, cookie_path, is_valid, last_checked_at) VALUES (?, 'webvpn', ?, 1, CURRENT_TIMESTAMP)" "$user_id" "$cookie_file"

shell_log_write INFO auth "webvpn login completed" "user_id=$user_id account=$campus_account email=$email cookie=$cookie_file" "$user_id"

account_json="$(shell_db_query "SELECT user_id, campus_account, webvpn_cookie_path, session_valid, last_login_at FROM campus_accounts WHERE user_id = ?" "$user_id")"
shell_response_json true "执行成功" "$account_json"
