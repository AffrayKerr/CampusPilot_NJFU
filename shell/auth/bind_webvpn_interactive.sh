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
user_dir="$(shell_env_ensure_user_runtime_dir "$user_id")"

bound_account_json="$(shell_db_query "SELECT user_id, campus_account FROM campus_accounts WHERE user_id = ?" "$user_id")"
if [[ "$bound_account_json" == "[]" ]]; then
  shell_log_write ERROR auth "interactive webvpn login failed: campus account not bound" "user_id=$user_id" "$user_id"
  shell_response_json false "campus account is not bound" null
  exit 1
fi
pid_file="$user_dir/selenium_login.pid"
status_file="$user_dir/selenium_login.status"
log_file="$user_dir/selenium_login.log"

# If a previous login process is still running, return its status
if [[ -f "$pid_file" ]]; then
  old_pid="$(cat "$pid_file" 2>/dev/null || echo '')"
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
    shell_response_json true "Browser login already in progress, please complete login in the browser window" \
      "{\"status\": \"in_progress\", \"pid\": $old_pid}"
    exit 0
  fi
  rm -f "$pid_file"
fi

# Clean up previous status
rm -f "$status_file" "$log_file"
echo "starting" > "$status_file"

script_path="$SCRIPT_DIR/webvpn_selenium_helper.py"
if [[ "$SELENIUM_PYTHON" == *.exe ]]; then
  script_path="$(wslpath -w "$script_path")"
fi

# Launch Selenium in background, write result to status_file when done
(
  if result="$("$SELENIUM_PYTHON" "$script_path" "$user_id" 2>"$log_file")"; then
    echo "$result" > "$status_file"
    "$AUTH_PYTHON" "$SCRIPT_DIR/webvpn_client.py" check "$user_id" >/dev/null 2>&1 || true
  else
    if [[ -n "$result" && "$result" == *'"success"'* ]]; then
      echo "$result" > "$status_file"
    else
      printf '{"success":false,"message":"interactive login failed","data":null}' > "$status_file"
    fi
  fi
  rm -f "$pid_file"
) &
bg_pid=$!
echo "$bg_pid" > "$pid_file"

shell_log_write INFO auth "interactive webvpn login started in background" "user_id=$user_id pid=$bg_pid" "$user_id"
shell_response_json true "Browser opened, please complete login in the browser window" \
  "{\"status\": \"in_progress\", \"pid\": $bg_pid}"
