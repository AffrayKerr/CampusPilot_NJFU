#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../auth/runtime.sh"
AUTH_PYTHON="$(shell_auth_python)"
source "$SCRIPT_DIR/../common/env.sh"
source "$SCRIPT_DIR/../common/response.sh"
source "$SCRIPT_DIR/../common/log.sh"
source "$SCRIPT_DIR/../common/db.sh"

user_id="${1:-}"

if [[ -z "$user_id" ]]; then
  shell_response_json false "user_id is required" null
  exit 1
fi

shell_db_init

uid_json="$(shell_db_query "SELECT id FROM users WHERE username = ? OR CAST(id AS TEXT) = ?" "$user_id" "$user_id")"
if [[ "$uid_json" == "[]" ]]; then
  shell_response_json false "user not found" null
  exit 1
fi
uid="$(echo "$uid_json" | "$AUTH_PYTHON" -c "import json,sys; d=json.load(sys.stdin); print(d[0]['id'] if d else '')")"

ns_json="$(shell_db_query "SELECT enable_email, enable_desktop, enable_schedule_reminder FROM notification_settings WHERE user_id = ?" "$uid")"
enable_email="$(echo "$ns_json" | "$AUTH_PYTHON" -c "import json,sys; d=json.load(sys.stdin); print(d[0]['enable_email'] if d else 0)" 2>/dev/null || echo "0")"
enable_desktop="$(echo "$ns_json" | "$AUTH_PYTHON" -c "import json,sys; d=json.load(sys.stdin); print(d[0]['enable_desktop'] if d else 1)" 2>/dev/null || echo "1")"
enable_schedule="$(echo "$ns_json" | "$AUTH_PYTHON" -c "import json,sys; d=json.load(sys.stdin); print(d[0]['enable_schedule_reminder'] if d else 1)" 2>/dev/null || echo "1")"

if [[ "$enable_email" == "0" && "$enable_desktop" == "0" ]]; then
  shell_log_write INFO notification "daily summary skipped: all channels disabled" "user_id=$user_id" "$user_id"
  shell_response_json true "Daily summary skipped (all channels disabled)" null
  exit 0
fi

summary="$("$AUTH_PYTHON" - "$DATABASE_PATH" "$uid" <<'PY'
import json
import sqlite3
import sys
from datetime import datetime

db_path = sys.argv[1]
uid = sys.argv[2]
today = datetime.now()
weekday = today.isoweekday()  # 1=Mon, 7=Sun
today_str = today.strftime("%Y-%m-%d")

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

courses = conn.execute(
    "SELECT course_name, section, classroom, teacher FROM schedules WHERE user_id = ? AND weekday = ?",
    (uid, weekday)
).fetchall()

exams = conn.execute(
    "SELECT course_name, exam_time, exam_location, seat_number FROM exams WHERE user_id = ? AND exam_time LIKE ?",
    (uid, f"{today_str}%")
).fetchall()

tasks = conn.execute(
    "SELECT title, deadline, priority FROM tasks WHERE user_id = ? AND status = 'pending' AND deadline LIKE ? ORDER BY priority DESC",
    (uid, f"{today_str}%")
).fetchall()

conn.close()

lines = [f"CampusPilot 每日待办 - {today_str}", "=" * 30]

if courses:
    lines.append(f"\n【今日课程】共 {len(courses)} 节")
    for c in courses:
        lines.append(f"  · {c['course_name']}  {c['section']}  {c['classroom'] or ''}  {c['teacher'] or ''}")
else:
    lines.append("\n【今日课程】无")

if exams:
    lines.append(f"\n【今日考试】共 {len(exams)} 场")
    for e in exams:
        seat = f"座位：{e['seat_number']}" if e['seat_number'] else ""
        lines.append(f"  · {e['course_name']}  {e['exam_time']}  {e['exam_location'] or ''}  {seat}")
else:
    lines.append("\n【今日考试】无")

if tasks:
    lines.append(f"\n【今日截止 DDL】共 {len(tasks)} 项")
    for t in tasks:
        priority_label = {"high": "高", "medium": "中", "low": "低"}.get(t['priority'], t['priority'])
        lines.append(f"  · [{priority_label}] {t['title']}  截止：{t['deadline']}")
else:
    lines.append("\n【今日截止 DDL】无")

lines.append("\n---\nCampusPilot 自动发送，请勿回复")

print(json.dumps({
    "summary": "\n".join(lines),
    "courses": len(courses),
    "exams": len(exams),
    "tasks": len(tasks),
    "date": today_str,
}))
PY
)"

if [[ -z "$summary" || "$summary" == *'"error"'* ]]; then
  shell_log_write ERROR notification "daily summary query failed" "user_id=$user_id" "$user_id"
  shell_response_json false "Failed to generate daily summary" null
  exit 1
fi

summary_text="$(echo "$summary" | "$AUTH_PYTHON" -c "import json,sys; d=json.loads(sys.stdin.read()); print(d['summary'])")"
summary_date="$(echo "$summary" | "$AUTH_PYTHON" -c "import json,sys; d=json.loads(sys.stdin.read()); print(d['date'])")"

sent_count=0

if [[ "$enable_desktop" == "1" && "$enable_schedule" == "1" ]]; then
  desktop_title="CampusPilot 每日待办 - $summary_date"
  desktop_body="$(echo "$summary" | "$AUTH_PYTHON" -c "
import json,sys
d=json.loads(sys.stdin.read())
parts=[]
if d['courses']: parts.append(f\"{d['courses']}节课\")
if d['exams']:   parts.append(f\"{d['exams']}场考试\")
if d['tasks']:   parts.append(f\"{d['tasks']}项DDL\")
print('今日：' + '、'.join(parts) if parts else '今日无待办事项')
")"
  bash "$SCRIPT_DIR/notify_desktop.sh" "$user_id" "$desktop_title" "$desktop_body" >/dev/null 2>&1 || true
  sent_count=$((sent_count + 1))
fi

if [[ "$enable_email" == "1" && "$enable_schedule" == "1" ]]; then
  email_subject="CampusPilot 每日待办 - $summary_date"
  bash "$SCRIPT_DIR/notify_email.sh" "$user_id" "$email_subject" "$summary_text" "" >/dev/null 2>&1 || true
  sent_count=$((sent_count + 1))
fi

shell_log_write INFO notification "daily summary sent" "user_id=$user_id date=$summary_date sent=$sent_count" "$user_id"
shell_response_json true "Daily summary sent" \
  "$(echo "$summary" | "$AUTH_PYTHON" -c "import json,sys; d=json.loads(sys.stdin.read()); d['sent_count']=$sent_count; del d['summary']; print(json.dumps(d))")"
