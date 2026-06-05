#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=runtime.sh
source "$SCRIPT_DIR/runtime.sh"
AUTH_PYTHON="$(shell_auth_python)"
SELENIUM_PYTHON="$(shell_selenium_python)"
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
  shell_log_write ERROR auth "interactive webvpn login failed: campus account not bound" "user_id=$user_id" "$user_id"
  shell_response_json false "campus account is not bound" null
  exit 1
fi

shell_log_write INFO auth "starting interactive webvpn login" "user_id=$user_id" "$user_id"

script_path="$SCRIPT_DIR/webvpn_selenium_helper.py"
if [[ "$SELENIUM_PYTHON" == *.exe ]]; then
  script_path="$(wslpath -w "$script_path")"
fi

if ! result_json="$("$SELENIUM_PYTHON" "$script_path" "$user_id" 2>/dev/null)"; then
  shell_log_write ERROR auth "interactive webvpn login failed" "user_id=$user_id" "$user_id"
  if [[ -z "$result_json" || "$result_json" != *'"success"'* ]]; then
    result_json="$(shell_response_json false "interactive login failed" null)"
  fi
  printf '%s\n' "$result_json"
  exit 1
fi

if ! check_result="$("$AUTH_PYTHON" "$SCRIPT_DIR/webvpn_client.py" check "$user_id" 2>&1)"; then
  shell_log_write WARNING auth "interactive login succeeded but session check failed" "user_id=$user_id" "$user_id"
fi

shell_log_write INFO auth "interactive webvpn login completed" "user_id=$user_id" "$user_id"
printf '%s\n' "$result_json"
