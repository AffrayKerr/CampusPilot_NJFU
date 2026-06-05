#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../auth/runtime.sh"
AUTH_PYTHON="$(shell_auth_python)"
source "$SCRIPT_DIR/../common/env.sh"
source "$SCRIPT_DIR/../common/response.sh"
source "$SCRIPT_DIR/../common/log.sh"
source "$SCRIPT_DIR/../common/db.sh"

feedback_id="${1:-}"

if [[ -z "$feedback_id" ]]; then
  shell_response_json false "feedback_id is required" null
  exit 1
fi

shell_db_init

fb_json="$(shell_db_query "SELECT user_id, title, status FROM feedbacks WHERE id = ?" "$feedback_id")"
if [[ "$fb_json" == "[]" ]]; then
  shell_response_json false "feedback not found" null
  exit 1
fi

user_id="$(echo "$fb_json" | "$AUTH_PYTHON" -c "import json,sys; d=json.load(sys.stdin); print(d[0]['user_id'] if d and d[0]['user_id'] else '')")"
fb_title="$(echo "$fb_json" | "$AUTH_PYTHON" -c "import json,sys; d=json.load(sys.stdin); print(d[0]['title'] if d else '')")"
fb_status="$(echo "$fb_json" | "$AUTH_PYTHON" -c "import json,sys; d=json.load(sys.stdin); print(d[0]['status'] if d else '')")"

if [[ -z "$user_id" ]]; then
  shell_log_write INFO notification "feedback notification skipped: anonymous" "feedback_id=$feedback_id" ""
  shell_response_json true "Feedback notification skipped (anonymous)" null
  exit 0
fi

ns_json="$(shell_db_query "SELECT enable_email, enable_desktop FROM notification_settings WHERE user_id = ?" "$user_id")"
enable_email="$(echo "$ns_json" | "$AUTH_PYTHON" -c "import json,sys; d=json.load(sys.stdin); print(d[0]['enable_email'] if d else 0)" 2>/dev/null || echo "0")"
enable_desktop="$(echo "$ns_json" | "$AUTH_PYTHON" -c "import json,sys; d=json.load(sys.stdin); print(d[0]['enable_desktop'] if d else 1)" 2>/dev/null || echo "1")"

notify_title="反馈状态更新"
notify_body="您的反馈「${fb_title}」状态已更新为：${fb_status}"

sent_count=0

if [[ "$enable_desktop" == "1" ]]; then
  bash "$SCRIPT_DIR/notify_desktop.sh" "$user_id" "$notify_title" "$notify_body" >/dev/null 2>&1 || true
  sent_count=$((sent_count + 1))
fi

if [[ "$enable_email" == "1" ]]; then
  bash "$SCRIPT_DIR/notify_email.sh" "$user_id" "$notify_title" "$notify_body" "" >/dev/null 2>&1 || true
  sent_count=$((sent_count + 1))
fi

shell_log_write INFO notification "feedback notification sent" \
  "feedback_id=$feedback_id user_id=$user_id status=$fb_status sent=$sent_count" "$user_id"
shell_response_json true "Feedback notification sent" \
  "{\"feedback_id\": $feedback_id, \"sent_count\": $sent_count}"
