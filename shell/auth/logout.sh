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
shell_cookie_delete "$user_id"
shell_db_execute "UPDATE campus_accounts SET webvpn_cookie_path = NULL, session_valid = 0, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?" "$user_id"
shell_db_execute "UPDATE sessions SET is_valid = 0, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND session_type = 'webvpn'" "$user_id"
shell_log_write INFO auth "webvpn logout completed" "user_id=$user_id cookie=$cookie_file" "$user_id"

shell_response_json true "执行成功" "{}"
