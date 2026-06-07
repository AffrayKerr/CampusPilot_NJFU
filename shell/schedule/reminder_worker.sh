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

compute_pending_reminders() {
  "$AUTH_PYTHON" - "$DATABASE_PATH" "$user_id" <<'PY'
import json, os, re, sqlite3, sys
from datetime import datetime, timedelta

SECTION_TIMES = {
    "1": "08:00", "2": "08:55", "3": "09:55", "4": "10:50",
    "5": "11:45", "6": "12:40", "7": "14:00", "8": "14:55",
    "9": "15:55", "10": "16:50", "11": "18:30", "12": "19:25", "13": "20:20",
}

def parse_datetime(value):
    text = str(value or "").strip().replace("T", " ")
    match = re.search(r"(\d{4}-\d{1,2}-\d{1,2})\s+(\d{1,2}:\d{2})", text)
    if match:
        text = f"{match.group(1)} {match.group(2)}"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except (ValueError, TypeError):
            continue
    return None

def section_start(section_str):
    nums = re.findall(r"\d+", str(section_str or ""))
    if not nums:
        return None
    return SECTION_TIMES.get(min(nums, key=int))

def get_current_week(today):
    start_str = os.environ.get("SEMESTER_START_DATE", "")
    if not start_str:
        return -1
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
    except ValueError:
        return -1
    delta = (today - start).days
    if delta < 0:
        return 0
    return delta // 7 + 1

def week_matches(week_info, current_week):
    if current_week <= 0 or not week_info:
        return True
    if re.search(r"单周|单$", week_info) and current_week % 2 == 0:
        return False
    if re.search(r"双周|双$", week_info) and current_week % 2 == 1:
        return False
    ranges = re.findall(r"(\d+)-(\d+)|(\d+)", week_info)
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
weekday = today.weekday() + 1
current_week = get_current_week(today)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT id FROM users WHERE username = ? OR CAST(id AS TEXT) = ?", (user_id, user_id))
user = cur.fetchone()
if not user:
    print(json.dumps([], ensure_ascii=False))
    conn.close()
    sys.exit(0)
uid = user["id"]

cur.execute(
    "SELECT enable_schedule_reminder, enable_email, enable_desktop FROM notification_settings WHERE user_id = ?",
    (uid,),
)
settings = cur.fetchone()
if settings and not settings["enable_schedule_reminder"]:
    print(json.dumps([], ensure_ascii=False))
    conn.close()
    sys.exit(0)

enable_email = bool(settings["enable_email"]) if settings else False
enable_desktop = bool(settings["enable_desktop"]) if settings else True
pending = []

# 周期性课程提醒
cur.execute(
    "SELECT r.id, r.remind_before_minutes, s.course_name, s.teacher, s.section, s.classroom, s.week_info, s.note "
    "FROM reminders r JOIN schedules s ON r.target_id = s.id "
    "WHERE r.user_id = ? AND r.target_type = 'schedule' AND r.enabled = 1 AND s.weekday = ?",
    (uid, weekday),
)
for row in cur.fetchall():
    if not week_matches(row["week_info"], current_week):
        continue
    start_time = section_start(row["section"])
    if not start_time:
        continue
    hour, minute = map(int, start_time.split(":"))
    class_dt = datetime(today.year, today.month, today.day, hour, minute)
    remind_dt = class_dt - timedelta(minutes=row["remind_before_minutes"])
    if remind_dt <= now < remind_dt + timedelta(minutes=1):
        pending.append({
            "reminder_id": row["id"],
            "reminder_source": "reminders",
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

# 一次性课程绝对提醒
cur.execute(
    "SELECT sar.id, sar.remind_at, s.course_name, s.teacher, s.section, s.classroom, s.note "
    "FROM schedule_absolute_reminders sar JOIN schedules s ON sar.schedule_id = s.id "
    "WHERE sar.user_id = ? AND sar.enabled = 1",
    (uid,),
)
for row in cur.fetchall():
    remind_dt = parse_datetime(row["remind_at"])
    if not remind_dt or remind_dt > now:
        continue
    pending.append({
        "reminder_id": row["id"],
        "reminder_source": "schedule_absolute_reminders",
        "type": "schedule_absolute",
        "title": row["course_name"],
        "teacher": row["teacher"] or "",
        "section": row["section"] or "",
        "location": row["classroom"] or "",
        "note": row["note"] or "",
        "remind_before_minutes": 0,
        "enable_email": enable_email,
        "enable_desktop": enable_desktop,
    })

# 考试提醒
cur.execute(
    "SELECT r.id, r.remind_before_minutes, e.course_name, e.exam_time, e.exam_location, e.seat_number, e.note "
    "FROM reminders r JOIN exams e ON r.target_id = e.id "
    "WHERE r.user_id = ? AND r.target_type = 'exam' AND r.enabled = 1",
    (uid,),
)
for row in cur.fetchall():
    exam_dt = parse_datetime(row["exam_time"])
    if not exam_dt:
        continue
    remind_dt = exam_dt - timedelta(minutes=row["remind_before_minutes"])
    if remind_dt <= now:
        pending.append({
            "reminder_id": row["id"],
            "reminder_source": "reminders",
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

# 任务提醒
cur.execute(
    "SELECT r.id, r.remind_before_minutes, t.title, t.category, t.priority, t.deadline, t.note "
    "FROM reminders r JOIN tasks t ON r.target_id = t.id "
    "WHERE r.user_id = ? AND r.target_type = 'task' AND r.enabled = 1 AND t.status = 'pending'",
    (uid,),
)
for row in cur.fetchall():
    deadline_dt = parse_datetime(row["deadline"])
    if not deadline_dt:
        continue
    remind_dt = deadline_dt - timedelta(minutes=row["remind_before_minutes"])
    if remind_dt <= now:
        pending.append({
            "reminder_id": row["id"],
            "reminder_source": "reminders",
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

build_notification_content() {
  local reminder_json="$1"
  "$AUTH_PYTHON" - "$reminder_json" <<'PY'
import json, sys

r = json.loads(sys.argv[1])
type_ = r["type"]
minutes = r.get("remind_before_minutes", 0)

if type_ == "schedule":
    title = f"课程提醒 · {r['title']}"
    body_parts = [f"还有 {minutes} 分钟上课"]
    if r.get("teacher"): body_parts.append(f"教师: {r['teacher']}")
    if r.get("section"): body_parts.append(f"节次: {r['section']}")
    if r.get("location"): body_parts.append(f"地点: {r['location']}")
    if r.get("note"): body_parts.append(f"备注: {r['note']}")
elif type_ == "schedule_absolute":
    title = f"课程提醒 · {r['title']}"
    body_parts = ["已到你设置的上课提醒时间"]
    if r.get("teacher"): body_parts.append(f"教师: {r['teacher']}")
    if r.get("section"): body_parts.append(f"节次: {r['section']}")
    if r.get("location"): body_parts.append(f"地点: {r['location']}")
    if r.get("note"): body_parts.append(f"备注: {r['note']}")
elif type_ == "exam":
    title = f"考试提醒 · {r['title']}"
    body_parts = [f"已到你设置的考试提醒时间（提前 {minutes} 分钟）"]
    if r.get("exam_time"): body_parts.append(f"考试时间: {r['exam_time']}")
    if r.get("location"): body_parts.append(f"地点: {r['location']}")
    if r.get("seat_number"): body_parts.append(f"座位号: {r['seat_number']}")
    if r.get("note"): body_parts.append(f"备注: {r['note']}")
else:
    title = f"任务提醒 · {r['title']}"
    body_parts = [f"已到你设置的任务提醒时间（提前 {minutes} 分钟）"]
    if r.get("deadline"): body_parts.append(f"截止时间: {r['deadline']}")
    if r.get("category"): body_parts.append(f"分类: {r['category']}")
    if r.get("priority"): body_parts.append(f"优先级: {r['priority']}")
    if r.get("note"): body_parts.append(f"备注: {r['note']}")

print(title)
print("\n".join(body_parts))
PY
}

send_one_reminder() {
  local reminder_json="$1"
  local notify_dir="$SCRIPT_DIR/../notification"
  local content title body enable_email enable_desktop reminder_type reminder_id reminder_source

  content="$(build_notification_content "$reminder_json")"
  title="$(printf '%s\n' "$content" | head -n 1)"
  body="$(printf '%s\n' "$content" | tail -n +2)"
  enable_email="$(printf '%s' "$reminder_json" | "$AUTH_PYTHON" -c "import sys,json; print(json.loads(sys.stdin.read()).get('enable_email', False))")"
  enable_desktop="$(printf '%s' "$reminder_json" | "$AUTH_PYTHON" -c "import sys,json; print(json.loads(sys.stdin.read()).get('enable_desktop', True))")"
  reminder_type="$(printf '%s' "$reminder_json" | "$AUTH_PYTHON" -c "import sys,json; print(json.loads(sys.stdin.read()).get('type', ''))")"
  reminder_id="$(printf '%s' "$reminder_json" | "$AUTH_PYTHON" -c "import sys,json; print(json.loads(sys.stdin.read()).get('reminder_id', ''))")"
  reminder_source="$(printf '%s' "$reminder_json" | "$AUTH_PYTHON" -c "import sys,json; print(json.loads(sys.stdin.read()).get('reminder_source', 'reminders'))")"

  if [[ "$enable_desktop" == "True" ]] && [[ -f "$notify_dir/notify_desktop.sh" ]]; then
    bash "$notify_dir/notify_desktop.sh" "$user_id" "$title" "$body" || true
  fi

  if [[ "$enable_email" == "True" ]] && [[ -f "$notify_dir/notify_email.sh" ]]; then
    bash "$notify_dir/notify_email.sh" "$user_id" "$title" "$body" "" || true
  fi

  shell_log_write INFO schedule "reminder sent: $title" "$body" "$user_id"

  if [[ -n "$reminder_id" && "$reminder_type" != "schedule" ]]; then
    if [[ "$reminder_source" == "schedule_absolute_reminders" ]]; then
      shell_db_execute \
        "UPDATE schedule_absolute_reminders SET enabled = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = (SELECT id FROM users WHERE username = ? OR CAST(id AS TEXT) = ?)" \
        "$reminder_id" "$user_id" "$user_id"
    else
      shell_db_execute \
        "UPDATE reminders SET enabled = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = (SELECT id FROM users WHERE username = ? OR CAST(id AS TEXT) = ?)" \
        "$reminder_id" "$user_id" "$user_id"
    fi
  fi
}

shell_log_write INFO schedule "reminder worker started" "user_id=$user_id" "$user_id"
pending_json="$(compute_pending_reminders)"
pending_count="$(printf '%s' "$pending_json" | "$AUTH_PYTHON" -c "import sys,json; print(len(json.loads(sys.stdin.read())))")"

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
done < <(printf '%s' "$pending_json" | "$AUTH_PYTHON" -c "import sys,json; [print(json.dumps(r, ensure_ascii=False)) for r in json.loads(sys.stdin.read())]")

shell_log_write INFO schedule "reminder worker finished" "user_id=$user_id sent=$sent_count" "$user_id"
shell_response_json true "Reminders sent" "{\"reminders_sent\": $sent_count}"
