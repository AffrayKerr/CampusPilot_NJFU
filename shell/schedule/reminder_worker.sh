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
if [[ -z "$user_id" ]]; then
  shell_response_json false "user_id is required" null
  exit 1
fi

shell_db_init
shell_env_ensure_user_runtime_dir "$user_id" >/dev/null

# ---------- compute_pending_reminders ----------
# Outputs a JSON array of reminders that are due right now.
# For schedules: uses SECTION_TIMES mapping + today's weekday + reminders.remind_before_minutes.
# For exams / tasks: compares absolute timestamp against current time.
compute_pending_reminders() {
  "$AUTH_PYTHON" - "$DATABASE_PATH" "$user_id" <<'PY'
import json, os, re, sqlite3, sys
from datetime import date, datetime, timedelta

SECTION_TIMES = {
    "1":  "08:00", "2":  "08:55",
    "3":  "09:55", "4":  "10:50",
    "5":  "11:45", "6":  "12:40",
    "7":  "14:00", "8":  "14:55",
    "9":  "15:55", "10": "16:50",
    "11": "18:30", "12": "19:25",
    "13": "20:20",
}

def section_start(section_str):
    """Return earliest start time for a section string like '1-2' or '3'."""
    nums = re.findall(r'\d+', str(section_str))
    if not nums:
        return None
    t = SECTION_TIMES.get(min(nums, key=int))
    if not t:
        return None
    return t  # "HH:MM"

def get_current_week(today):
    start_str = os.environ.get("SEMESTER_START_DATE", "")
    if not start_str:
        return -1
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
        delta = (today - start).days
        if delta < 0:
            return 0
        return delta // 7 + 1
    except ValueError:
        return -1

def week_matches(week_info, current_week):
    if current_week <= 0 or not week_info:
        return True
    if re.search(r'单周|单$', week_info) and current_week % 2 == 0:
        return False
    if re.search(r'双周|双$', week_info) and current_week % 2 == 1:
        return False
    ranges = re.findall(r'(\d+)-(\d+)|(\d+)', week_info)
    if not ranges:
        return True
    for r_start, r_end, single in ranges:
        if single and current_week == int(single):
            return True
        if r_start and r_end and int(r_start) <= current_week <= int(r_end):
            return True
    return False

db_path = sys.argv[1]
user_id = sys.argv[2]
now = datetime.now().replace(second=0, microsecond=0)
today = now.date()
weekday = today.weekday() + 1  # 1=Mon … 7=Sun
current_week = get_current_week(today)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute(
    "SELECT id FROM users WHERE username = ? OR CAST(id AS TEXT) = ?",
    (user_id, user_id)
)
row = cur.fetchone()
if not row:
    print(json.dumps([]))
    conn.close()
    sys.exit(0)
uid = row["id"]

cur.execute(
    "SELECT enable_schedule_reminder, enable_email, enable_desktop "
    "FROM notification_settings WHERE user_id = ?",
    (uid,)
)
ns = cur.fetchone()
if ns and not ns["enable_schedule_reminder"]:
    print(json.dumps([]))
    conn.close()
    sys.exit(0)

enable_email   = bool(ns["enable_email"])   if ns else False
enable_desktop = bool(ns["enable_desktop"]) if ns else True

pending = []

# --- schedule reminders (periodic, based on today's weekday) ---
cur.execute(
    "SELECT r.id, r.remind_before_minutes, "
    "       s.course_name, s.teacher, s.section, s.classroom, s.week_info, s.note "
    "FROM reminders r "
    "JOIN schedules s ON r.target_id = s.id "
    "WHERE r.user_id = ? AND r.target_type = 'schedule' AND r.enabled = 1 "
    "  AND s.weekday = ?",
    (uid, weekday)
)
for row in cur.fetchall():
    if not week_matches(row["week_info"], current_week):
        continue
    t = section_start(row["section"])
    if not t:
        continue
    h, m = map(int, t.split(":"))
    class_dt = datetime(today.year, today.month, today.day, h, m)
    remind_dt = class_dt - timedelta(minutes=row["remind_before_minutes"])
    # Fire within a 1-minute window so a per-minute cron doesn't double-fire
    if remind_dt <= now < remind_dt + timedelta(minutes=1):
        pending.append({
            "reminder_id": row["id"],
            "type": "schedule",
            "title": row["course_name"],
            "teacher": row["teacher"] or "",
            "section": row["section"] or "",
            "location": row["classroom"] or "",
            "note": row["note"] or "",
            "remind_before_minutes": row["remind_before_minutes"],
            "enable_email": enable_email,
            "enable_desktop": enable_desktop,
        })

# --- exam reminders ---
cur.execute(
    "SELECT r.id, r.remind_before_minutes, "
    "       e.course_name, e.exam_time, e.exam_location, e.seat_number, e.note "
    "FROM reminders r "
    "JOIN exams e ON r.target_id = e.id "
    "WHERE r.user_id = ? AND r.target_type = 'exam' AND r.enabled = 1",
    (uid,)
)
for row in cur.fetchall():
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            exam_dt = datetime.strptime(row["exam_time"], fmt)
            break
        except (ValueError, TypeError):
            exam_dt = None
    if not exam_dt:
        continue
    remind_dt = exam_dt - timedelta(minutes=row["remind_before_minutes"])
    if remind_dt <= now < remind_dt + timedelta(minutes=1):
        pending.append({
            "reminder_id": row["id"],
            "type": "exam",
            "title": row["course_name"],
            "exam_time": row["exam_time"],
            "location": row["exam_location"] or "",
            "seat_number": row["seat_number"] or "",
            "note": row["note"] or "",
            "remind_before_minutes": row["remind_before_minutes"],
            "enable_email": enable_email,
            "enable_desktop": enable_desktop,
        })

# --- task reminders ---
cur.execute(
    "SELECT r.id, r.remind_before_minutes, "
    "       t.title, t.category, t.priority, t.deadline, t.note "
    "FROM reminders r "
    "JOIN tasks t ON r.target_id = t.id "
    "WHERE r.user_id = ? AND r.target_type = 'task' AND r.enabled = 1 AND t.status = 'pending'",
    (uid,)
)
for row in cur.fetchall():
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            deadline_dt = datetime.strptime(row["deadline"], fmt)
            break
        except (ValueError, TypeError):
            deadline_dt = None
    if not deadline_dt:
        continue
    remind_dt = deadline_dt - timedelta(minutes=row["remind_before_minutes"])
    if remind_dt <= now < remind_dt + timedelta(minutes=1):
        pending.append({
            "reminder_id": row["id"],
            "type": "task",
            "title": row["title"],
            "category": row["category"] or "",
            "priority": row["priority"] or "medium",
            "deadline": row["deadline"],
            "note": row["note"] or "",
            "remind_before_minutes": row["remind_before_minutes"],
            "enable_email": enable_email,
            "enable_desktop": enable_desktop,
        })

conn.close()
print(json.dumps(pending, ensure_ascii=False))
PY
}

# ---------- build_notification_content ----------
# $1 = single reminder JSON object; echoes "TITLE\nBODY"
build_notification_content() {
  local r="$1"
  "$AUTH_PYTHON" - "$r" <<'PY'
import json, sys

r = json.loads(sys.argv[1])
t = r["type"]
minutes = r["remind_before_minutes"]

if t == "schedule":
    title = f"课程提醒 · {r['title']}"
    body_parts = [f"还有 {minutes} 分钟上课"]
    if r.get("teacher"):  body_parts.append(f"教师: {r['teacher']}")
    if r.get("section"):  body_parts.append(f"节次: {r['section']}")
    if r.get("location"): body_parts.append(f"地点: {r['location']}")
    if r.get("note"):     body_parts.append(f"备注: {r['note']}")

elif t == "exam":
    title = f"考试提醒 · {r['title']}"
    body_parts = [f"还有 {minutes} 分钟考试"]
    if r.get("exam_time"):    body_parts.append(f"时间: {r['exam_time']}")
    if r.get("location"):     body_parts.append(f"地点: {r['location']}")
    if r.get("seat_number"):  body_parts.append(f"座位号: {r['seat_number']}")
    if r.get("note"):         body_parts.append(f"备注: {r['note']}")

else:  # task
    title = f"任务提醒 · {r['title']}"
    body_parts = [f"截止时间: {r['deadline']}（还有 {minutes} 分钟）"]
    if r.get("category"): body_parts.append(f"分类: {r['category']}")
    if r.get("priority"): body_parts.append(f"优先级: {r['priority']}")
    if r.get("note"):     body_parts.append(f"备注: {r['note']}")

print(title)
print("\n".join(body_parts))
PY
}

# ---------- send_one_reminder ----------
send_one_reminder() {
  local reminder_json="$1"
  local notify_dir="$SCRIPT_DIR/../notification"

  local content title body enable_email enable_desktop
  content="$(build_notification_content "$reminder_json")"
  title="$(echo "$content" | head -n 1)"
  body="$(echo "$content" | tail -n +2)"

  enable_email="$(echo "$reminder_json" | "$AUTH_PYTHON" -c "import sys,json; print(json.loads(sys.stdin.read()).get('enable_email', False))")"
  enable_desktop="$(echo "$reminder_json" | "$AUTH_PYTHON" -c "import sys,json; print(json.loads(sys.stdin.read()).get('enable_desktop', True))")"

  if [[ "$enable_desktop" == "True" ]] && [[ -f "$notify_dir/notify_desktop.sh" ]]; then
    bash "$notify_dir/notify_desktop.sh" "$user_id" "$title" "$body" || true
  fi

  if [[ "$enable_email" == "True" ]] && [[ -f "$notify_dir/notify_email.sh" ]]; then
    bash "$notify_dir/notify_email.sh" "$user_id" "$title" "$body" "" || true
  fi

  shell_db_execute \
    "INSERT INTO logs (user_id, module, level, message, detail) VALUES ((SELECT id FROM users WHERE username = ? OR CAST(id AS TEXT) = ?), 'schedule', 'INFO', ?, ?)" \
    "$user_id" "$user_id" "reminder sent: $title" "$body"
}

# ---------- main ----------
shell_log_write INFO schedule "reminder worker started" "user_id=$user_id" "$user_id"

pending_json="$(compute_pending_reminders)"
pending_count="$(echo "$pending_json" | "$AUTH_PYTHON" -c "import sys,json; print(len(json.loads(sys.stdin.read())))")"

if [[ "$pending_count" == "0" ]]; then
  shell_log_write INFO schedule "no pending reminders" "user_id=$user_id" "$user_id"
  shell_response_json true "No pending reminders" '{"reminders_sent": 0}'
  exit 0
fi

sent_count=0
while IFS= read -r reminder_line; do
  if send_one_reminder "$reminder_line"; then
    sent_count=$((sent_count + 1))
  fi
done < <(echo "$pending_json" | "$AUTH_PYTHON" -c "import sys,json; [print(json.dumps(r)) for r in json.loads(sys.stdin.read())]")

shell_log_write INFO schedule "reminder worker finished" "user_id=$user_id sent=$sent_count" "$user_id"
shell_response_json true "Reminders sent" "{\"reminders_sent\": $sent_count}"
