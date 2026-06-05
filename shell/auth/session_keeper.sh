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
user_dir="$(shell_env_ensure_user_runtime_dir "$user_id")"
needs_relogin_flag="$user_dir/needs_relogin"
keeper_lock="$user_dir/session_keeper.lock"

# Prevent concurrent runs for the same user
if [[ -f "$keeper_lock" ]]; then
  lock_pid="$(cat "$keeper_lock" 2>/dev/null || echo '')"
  if [[ -n "$lock_pid" ]] && kill -0 "$lock_pid" 2>/dev/null; then
    shell_log_write INFO auth "session keeper already running" "user_id=$user_id pid=$lock_pid" "$user_id"
    shell_response_json true "Session keeper already running" "{\"pid\": $lock_pid}"
    exit 0
  fi
fi
echo $$ > "$keeper_lock"
trap 'rm -f "$keeper_lock"' EXIT

bound_json="$(shell_db_query "SELECT user_id FROM campus_accounts WHERE user_id = ?" "$user_id")"
if [[ "$bound_json" == "[]" ]]; then
  shell_log_write WARNING auth "session keeper skipped: campus account not bound" "user_id=$user_id" "$user_id"
  shell_response_json false "campus account is not bound" null
  exit 1
fi

# --- Step 1: check current session ---
check_result="$("$AUTH_PYTHON" "$SCRIPT_DIR/webvpn_client.py" check "$user_id" 2>&1 || true)"
if [[ "$check_result" == *'"success": true'* || "$check_result" == *'"success":true'* ]]; then
  rm -f "$needs_relogin_flag"
  shell_log_write INFO auth "session keeper: session still valid" "user_id=$user_id" "$user_id"
  shell_response_json true "Session is valid" '{"status": "valid"}'
  exit 0
fi

shell_log_write WARNING auth "session keeper: session expired, trying silent relogin" "user_id=$user_id" "$user_id"

# --- Step 2: try silent relogin with saved credentials ---
login_result="$("$AUTH_PYTHON" "$SCRIPT_DIR/webvpn_client.py" login "$user_id" 2>&1 || true)"
if [[ "$login_result" == *'"success": true'* || "$login_result" == *'"success":true'* ]]; then
  rm -f "$needs_relogin_flag"
  shell_log_write INFO auth "session keeper: silent relogin succeeded" "user_id=$user_id" "$user_id"
  shell_response_json true "Session renewed silently" '{"status": "renewed"}'
  exit 0
fi

# --- Step 3: silent relogin failed (likely captcha) — flag user for interactive relogin ---
shell_log_write WARNING auth "session keeper: silent relogin failed, user interaction required" "user_id=$user_id reason=$login_result" "$user_id"

echo "$(date -Iseconds)" > "$needs_relogin_flag"

shell_db_execute \
  "UPDATE campus_accounts SET session_valid = 0, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?" \
  "$user_id"

notify_dir="$SCRIPT_DIR/../notification"
if [[ -f "$notify_dir/notify_desktop.sh" ]]; then
  bash "$notify_dir/notify_desktop.sh" "$user_id" \
    "WebVPN 需要重新登录" \
    "自动登录失败（可能触发了验证码），请在 CampusPilot 个人中心重新进行交互式登录。" || true
fi

shell_response_json false "Session expired and silent relogin failed; interactive relogin required" \
  '{"status": "needs_relogin"}'
exit 1
