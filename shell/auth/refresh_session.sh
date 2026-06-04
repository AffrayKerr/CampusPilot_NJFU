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

user_id="${1:-}"
if [[ -z "$user_id" ]]; then
  shell_response_json false "user_id is required" null
  exit 1
fi

shell_db_init
cookie_file="$(shell_cookie_path "$user_id")"
if [[ ! -f "$cookie_file" ]]; then
  shell_log_write WARNING auth "refresh failed: cookie missing" "user_id=$user_id" "$user_id"
  shell_response_json false "session cookie not found" null
  exit 1
fi

session_valid="$(shell_db_query "SELECT session_valid FROM campus_accounts WHERE user_id = ?" "$user_id")"
if [[ "$session_valid" == "[]" ]]; then
  shell_log_write ERROR auth "refresh failed: campus account missing" "user_id=$user_id" "$user_id"
  shell_response_json false "campus account is not bound" null
  exit 1
fi

check_result="$("$SCRIPT_DIR/check_session.sh" "$user_id" 2>/dev/null || true)"
if [[ "$check_result" == *'"success":true'* ]]; then
  shell_db_execute "UPDATE campus_accounts SET session_valid = 1, last_login_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?" "$user_id"
  shell_log_write INFO auth "webvpn session refreshed" "user_id=$user_id cookie=$cookie_file" "$user_id"
  result_json="$(shell_db_query "SELECT session_valid, webvpn_cookie_path, last_login_at FROM campus_accounts WHERE user_id = ?" "$user_id")"
  shell_response_json true "执行成功" "$result_json"
  exit 0
fi

login_result="$("$SCRIPT_DIR/login_bound.sh" "$user_id" 2>/dev/null || true)"
if [[ "$login_result" == *'"success":true'* ]]; then
  shell_log_write INFO auth "webvpn session refreshed by relogin" "user_id=$user_id" "$user_id"
  shell_response_json true "执行成功" "$(shell_db_query "SELECT session_valid, webvpn_cookie_path, last_login_at FROM campus_accounts WHERE user_id = ?" "$user_id")"
  exit 0
fi

shell_log_write ERROR auth "webvpn session refresh failed" "user_id=$user_id" "$user_id"
shell_response_json false "session refresh failed" null
