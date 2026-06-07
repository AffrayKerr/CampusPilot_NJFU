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

feedback_id="${1:-}"
if [[ -z "$feedback_id" ]]; then
  shell_response_json false "feedback_id is required" null
  exit 1
fi

shell_db_init

fb_json="$(shell_db_query "SELECT f.id, f.user_id, f.type, f.title, f.content, f.contact_email, f.priority, f.created_at, u.username FROM feedbacks f LEFT JOIN users u ON u.id = f.user_id WHERE f.id = ?" "$feedback_id")"
if [[ "$fb_json" == "[]" ]]; then
  shell_response_json false "feedback not found" null
  exit 1
fi

feedback_user_id="$(echo "$fb_json" | "$AUTH_PYTHON" -c "import json,sys; d=json.load(sys.stdin); print(d[0].get('user_id') or 0)")"
subject="$(echo "$fb_json" | "$AUTH_PYTHON" -c "import json,sys; d=json.load(sys.stdin); print('[CampusPilot反馈] ' + d[0]['title'])")"
body="$(echo "$fb_json" | "$AUTH_PYTHON" -c "import json,sys; d=json.load(sys.stdin)[0]; print('反馈编号：{}\n反馈用户：{}\n反馈类型：{}\n优先级：{}\n联系邮箱：{}\n提交时间：{}\n\n反馈内容：\n{}'.format(d['id'], d.get('username') or 'anonymous', d['type'], d.get('priority') or 'medium', d.get('contact_email') or '未填写', d.get('created_at') or '-', d['content']))")"

recipients_json="$(shell_db_query "SELECT feedback_email FROM admin_settings WHERE receive_feedback_email = 1 AND feedback_email IS NOT NULL AND feedback_email != ''")"
recipients_csv="$(echo "$recipients_json" | "$AUTH_PYTHON" -c "import json,sys; rows=json.load(sys.stdin); print(','.join(row['feedback_email'] for row in rows if row.get('feedback_email')))" 2>/dev/null || echo "")"

if [[ -z "$recipients_csv" ]]; then
  recipients_csv="${SMTP_USER:-}"
fi

if [[ -z "$recipients_csv" ]]; then
  shell_log_write WARNING notification "feedback email skipped: no admin recipient configured" "feedback_id=$feedback_id" "$feedback_user_id"
  shell_response_json false "No admin feedback email configured" null
  exit 1
fi

sent_count=0
while IFS= read -r recipient; do
  [[ -z "$recipient" ]] && continue
  if bash "$SCRIPT_DIR/notify_email.sh" "$feedback_user_id" "$subject" "$body" "$recipient" >/dev/null 2>&1; then
    sent_count=$((sent_count + 1))
  fi
done < <(echo "$recipients_csv" | tr ',' '\n')

if [[ "$sent_count" -eq 0 ]]; then
  shell_log_write ERROR notification "feedback email send failed" "feedback_id=$feedback_id recipients=$recipients_csv" "$feedback_user_id"
  shell_response_json false "Feedback email send failed" null
  exit 1
fi

shell_log_write INFO notification "feedback email sent" "feedback_id=$feedback_id recipients=$recipients_csv sent=$sent_count" "$feedback_user_id"
shell_response_json true "Feedback email sent" "{\"feedback_id\": $feedback_id, \"sent_count\": $sent_count}"
