#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../auth/runtime.sh
source "$SCRIPT_DIR/../auth/runtime.sh"
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
seat_no="${2:-}"
status="${3:-}"
detail="${4:-}"

if [[ -z "$user_id" || -z "$seat_no" || -z "$status" ]]; then
  shell_response_json false "user_id, seat_no, and status are required" null
  exit 1
fi

shell_db_init

ns_json="$(shell_db_query "SELECT enable_email, enable_desktop, enable_seat_result FROM notification_settings WHERE user_id = (SELECT id FROM users WHERE username = ? OR CAST(id AS TEXT) = ?)" "$user_id" "$user_id")"
enable_email="$(echo "$ns_json" | "$AUTH_PYTHON" -c "import json,sys; d=json.load(sys.stdin); print(d[0]['enable_email'] if d else 0)" 2>/dev/null || echo "0")"
enable_desktop="$(echo "$ns_json" | "$AUTH_PYTHON" -c "import json,sys; d=json.load(sys.stdin); print(d[0]['enable_desktop'] if d else 1)" 2>/dev/null || echo "1")"
enable_seat_result="$(echo "$ns_json" | "$AUTH_PYTHON" -c "import json,sys; d=json.load(sys.stdin); print(d[0]['enable_seat_result'] if d else 1)" 2>/dev/null || echo "1")"

if [[ "$enable_seat_result" == "0" ]]; then
  shell_log_write INFO notification "seat result notification skipped (disabled)" "user_id=$user_id seat=$seat_no" "$user_id"
  shell_response_json true "Seat result notification skipped (disabled by user)" null
  exit 0
fi

if [[ "$status" == "success" ]]; then
  title="抢座成功"
  body="座位 $seat_no 已成功预约"
  [[ -n "$detail" ]] && body="$body（$detail）"
else
  title="抢座失败"
  body="座位 $seat_no 预约失败"
  [[ -n "$detail" ]] && body="$body（$detail）"
fi

sent_count=0

if [[ "$enable_desktop" == "1" ]]; then
  bash "$SCRIPT_DIR/notify_desktop.sh" "$user_id" "$title" "$body" >/dev/null 2>&1 || true
  sent_count=$((sent_count + 1))
fi

if [[ "$enable_email" == "1" ]]; then
  bash "$SCRIPT_DIR/notify_email.sh" "$user_id" "$title" "$body" "" >/dev/null 2>&1 || true
  sent_count=$((sent_count + 1))
fi

shell_log_write INFO notification "seat result notified" "user_id=$user_id seat=$seat_no status=$status sent=$sent_count" "$user_id"
shell_response_json true "Seat result notification sent" "{\"seat_no\": \"$seat_no\", \"status\": \"$status\", \"sent_count\": $sent_count}"
