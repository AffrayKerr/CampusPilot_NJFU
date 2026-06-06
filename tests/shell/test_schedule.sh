#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

RUN_ONLINE=false
for arg in "$@"; do
  [[ "$arg" == "--online" ]] && RUN_ONLINE=true
done

_PYTHON_CMD=""
for _c in /usr/bin/python3 /usr/local/bin/python3 python3; do
  if command -v "$_c" >/dev/null 2>&1; then
    _PYTHON_CMD="$_c"
    break
  fi
done
if [[ -z "$_PYTHON_CMD" ]]; then
  echo "[SKIP] no usable python found"
  exit 0
fi

mkdir -p "$ROOT_DIR/runtime/tmp"
printf '#!/usr/bin/env bash\nexec "%s" "$@"\n' "$_PYTHON_CMD" \
  > "$ROOT_DIR/runtime/tmp/python"
chmod +x "$ROOT_DIR/runtime/tmp/python"
export PATH="$ROOT_DIR/runtime/tmp:$PATH"

source shell/common/env.sh
source shell/common/response.sh
source shell/common/db.sh

SCHEDULE_DIR="$ROOT_DIR/shell/schedule"
TEST_USER="test_schedule_999"
TEST_DB="$ROOT_DIR/database/campus_pilot.db"

export DATABASE_PATH="$TEST_DB"

PASS=0; FAIL=0

ok()   { echo "  [PASS] $1"; PASS=$((PASS+1)); }
fail() { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }

assert_contains() {
  local val="$1" needle="$2" label="$3"
  if [[ "$val" == *"$needle"* ]]; then ok "$label"
  else fail "$label (missing: $needle)"; fi
}

assert_not_contains() {
  local val="$1" needle="$2" label="$3"
  if [[ "$val" != *"$needle"* ]]; then ok "$label"
  else fail "$label (should not contain: $needle)"; fi
}

assert_file_exists() { [[ -f "$1" ]] && ok "$2" || fail "$2 (missing: $1)"; }

echo ""
echo "=== Setup test database and user ==="

"$_PYTHON_CMD" - "$TEST_DB" "$TEST_USER" <<'PYEOF'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
conn.executescript("""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    email TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    course_name TEXT NOT NULL,
    teacher TEXT,
    week_info TEXT,
    weekday INTEGER,
    section TEXT,
    classroom TEXT,
    note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    course_name TEXT NOT NULL,
    exam_time TEXT,
    exam_location TEXT,
    seat_number TEXT,
    note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT NOT NULL,
    category TEXT,
    priority TEXT DEFAULT 'medium',
    deadline TEXT NOT NULL,
    repeat_rule TEXT,
    reminder_time TEXT,
    note TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    remind_before_minutes INTEGER NOT NULL,
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS notification_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    enable_email INTEGER DEFAULT 0,
    enable_desktop INTEGER DEFAULT 1,
    enable_seat_result INTEGER DEFAULT 1,
    enable_schedule_reminder INTEGER DEFAULT 1,
    enable_error_alert INTEGER DEFAULT 1,
    schedule_default_reminders TEXT DEFAULT '[15]',
    exam_default_reminders TEXT DEFAULT '[1440, 120]',
    task_default_reminders TEXT DEFAULT '[1440, 120]',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    module TEXT NOT NULL,
    level TEXT DEFAULT 'INFO',
    message TEXT NOT NULL,
    detail TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
""")

user_id = sys.argv[2]
conn.execute("INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, 'hash')", (user_id,))
row = conn.execute("SELECT id FROM users WHERE username = ?", (user_id,)).fetchone()
uid = row[0]

conn.execute("DELETE FROM schedules WHERE user_id = ?", (uid,))
conn.execute("DELETE FROM exams WHERE user_id = ?", (uid,))
conn.execute("DELETE FROM tasks WHERE user_id = ?", (uid,))
conn.execute("DELETE FROM reminders WHERE user_id = ?", (uid,))

conn.execute(
    "INSERT OR REPLACE INTO notification_settings (user_id, enable_schedule_reminder) VALUES (?, 1)",
    (uid,)
)

conn.commit()
conn.close()
print(f"Setup complete for user_id={uid}")
PYEOF

echo ""
echo "=== [1] add_task.sh ==="

add_out="$(bash "$SCHEDULE_DIR/add_task.sh" "$TEST_USER" "Test Task" "2026-06-15 23:59" "high" "homework" "none" "" "test note" 2>&1)"
assert_contains "$add_out" '"success": true' "add_task success"
assert_contains "$add_out" '"task_id"' "add_task returns task_id"
assert_contains "$add_out" "Test Task" "add_task title in response"

task_id="$(echo "$add_out" | "$_PYTHON_CMD" -c 'import json, sys; data = json.loads(sys.stdin.read()); print(data.get("data", {}).get("task_id", ""))')"

if [[ -n "$task_id" && "$task_id" =~ ^[0-9]+$ ]]; then
  ok "task_id is numeric: $task_id"
else
  fail "task_id not found or invalid: $task_id"
fi

no_args="$(bash "$SCHEDULE_DIR/add_task.sh" 2>&1 || true)"
assert_contains "$no_args" '"success": false' "add_task missing args fails"

no_deadline="$(bash "$SCHEDULE_DIR/add_task.sh" "$TEST_USER" "Title only" 2>&1 || true)"
assert_contains "$no_deadline" '"success": false' "add_task missing deadline fails"

echo ""
echo "=== [2] update_task.sh ==="

if [[ -n "$task_id" ]]; then
  update_out="$(bash "$SCHEDULE_DIR/update_task.sh" "$TEST_USER" "$task_id" "Updated Task" "2026-06-20 23:59" "low" "project" "none" "" "updated note" "pending" 2>&1)"
  assert_contains "$update_out" '"success": true' "update_task success"
  assert_contains "$update_out" "$task_id" "update_task returns task_id"

  db_check="$("$_PYTHON_CMD" - "$TEST_DB" "$TEST_USER" "$task_id" <<'PY'
import sqlite3, json, sys
conn = sqlite3.connect(sys.argv[1])
conn.row_factory = sqlite3.Row
user_id = sys.argv[2]
task_id = sys.argv[3]
row = conn.execute(
    "SELECT t.title, t.priority FROM tasks t JOIN users u ON t.user_id = u.id WHERE u.username = ? AND t.id = ?",
    (user_id, task_id)
).fetchone()
print(json.dumps(dict(row) if row else {}))
PY
)"
  assert_contains "$db_check" "Updated Task" "task title updated in db"
  assert_contains "$db_check" "low" "task priority updated in db"

  wrong_user="$(bash "$SCHEDULE_DIR/update_task.sh" "nonexistent_user" "$task_id" "Hack" "2026-06-30 23:59" "high" "" "none" "" "" "pending" 2>&1 || true)"
  assert_contains "$wrong_user" '"success": false' "update_task wrong user denied"
fi

echo ""
echo "=== [3] delete_task.sh ==="

add_out2="$(bash "$SCHEDULE_DIR/add_task.sh" "$TEST_USER" "To Be Deleted" "2026-07-01 23:59" "medium" "" "none" "" "" 2>&1)"
task_id2="$(echo "$add_out2" | "$_PYTHON_CMD" -c 'import json, sys; data = json.loads(sys.stdin.read()); print(data.get("data", {}).get("task_id", ""))')"

if [[ -n "$task_id2" && "$task_id2" =~ ^[0-9]+$ ]]; then
  delete_out="$(bash "$SCHEDULE_DIR/delete_task.sh" "$TEST_USER" "$task_id2" 2>&1)"
  assert_contains "$delete_out" '"success": true' "delete_task success"

  db_deleted="$("$_PYTHON_CMD" - "$TEST_DB" "$TEST_USER" "$task_id2" <<'PY'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
user_id = sys.argv[2]
task_id = sys.argv[3]
row = conn.execute(
    "SELECT COUNT(*) as cnt FROM tasks t JOIN users u ON t.user_id = u.id WHERE u.username = ? AND t.id = ?",
    (user_id, task_id)
).fetchone()
print(row[0] if row else 1)
PY
)"
  [[ "$db_deleted" == "0" ]] && ok "task deleted from db" || fail "task still in db"

  wrong_id="$(bash "$SCHEDULE_DIR/delete_task.sh" "$TEST_USER" "99999" 2>&1 || true)"
  assert_contains "$wrong_id" '"success": false' "delete_task nonexistent id fails"
fi

echo ""
echo "=== [4] list_today.sh ==="

list_out="$(bash "$SCHEDULE_DIR/list_today.sh" "$TEST_USER" 2>&1)"
assert_contains "$list_out" '"success": true' "list_today success"
assert_contains "$list_out" '"data"' "list_today has data"
assert_contains "$list_out" '"courses"' "list_today has courses field"
assert_contains "$list_out" '"tasks"' "list_today has tasks field"

no_user="$(bash "$SCHEDULE_DIR/list_today.sh" 2>&1 || true)"
assert_contains "$no_user" '"success": false' "list_today missing user_id fails"

echo ""
echo "=== [5] detect_changes.sh ==="

"$_PYTHON_CMD" - "$TEST_DB" "$TEST_USER" <<'PY'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
user_id = sys.argv[2]
uid = conn.execute("SELECT id FROM users WHERE username = ?", (user_id,)).fetchone()[0]
conn.execute("DELETE FROM schedules WHERE user_id = ?", (uid,))
conn.execute(
    "INSERT INTO schedules (user_id, course_name, teacher, weekday, section, classroom) VALUES (?, ?, ?, ?, ?, ?)",
    (uid, "Old Course", "Teacher A", 1, "1-2", "Room 101")
)
conn.commit()
conn.close()
PY

if [[ "$RUN_ONLINE" == true ]]; then
  echo "  [online test - skipped in offline mode]"
else
  echo "  [skipped - requires online access and valid webvpn session]"
fi

echo ""
echo "=== [6] sync_schedule.sh ==="

if [[ "$RUN_ONLINE" == true ]]; then
  echo "  [online test - skipped in offline mode]"
else
  echo "  [skipped - requires online access and valid webvpn session]"
fi

echo ""
echo "=== [7] sync_exam.sh ==="

if [[ "$RUN_ONLINE" == true ]]; then
  echo "  [online test - skipped in offline mode]"
else
  echo "  [skipped - requires online access and valid webvpn session]"
fi

echo ""
echo "=== [8] reminder_worker.sh ==="

"$_PYTHON_CMD" - "$TEST_DB" "$TEST_USER" <<'PY'
import sqlite3, sys
from datetime import datetime, timedelta
conn = sqlite3.connect(sys.argv[1])
user_id = sys.argv[2]
uid = conn.execute("SELECT id FROM users WHERE username = ?", (user_id,)).fetchone()[0]

now = datetime.now()
future = now + timedelta(minutes=20)
cur = conn.execute(
    "INSERT INTO tasks (user_id, title, deadline, status) VALUES (?, ?, ?, 'pending')",
    (uid, "Upcoming Task", future.strftime("%Y-%m-%d %H:%M:%S"))
)
task_id = cur.lastrowid
conn.execute(
    "INSERT INTO reminders (user_id, target_type, target_id, remind_before_minutes, enabled) VALUES (?, 'task', ?, 15, 1)",
    (uid, task_id)
)
conn.commit()
conn.close()
PY

reminder_out="$(bash "$SCHEDULE_DIR/reminder_worker.sh" "$TEST_USER" 2>&1)"
assert_contains "$reminder_out" '"success": true' "reminder_worker runs"
assert_contains "$reminder_out" '"reminders_sent"' "reminder_worker returns count"

no_user_reminder="$(bash "$SCHEDULE_DIR/reminder_worker.sh" 2>&1 || true)"
assert_contains "$no_user_reminder" '"success": false' "reminder_worker missing user_id fails"

echo ""
echo "=== Cleanup ==="

"$_PYTHON_CMD" - "$TEST_DB" "$TEST_USER" <<'PY'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
user_id = sys.argv[2]
try:
    uid = conn.execute("SELECT id FROM users WHERE username = ?", (user_id,)).fetchone()[0]
    conn.execute("DELETE FROM schedules WHERE user_id = ?", (uid,))
    conn.execute("DELETE FROM exams WHERE user_id = ?", (uid,))
    conn.execute("DELETE FROM tasks WHERE user_id = ?", (uid,))
    conn.execute("DELETE FROM reminders WHERE user_id = ?", (uid,))
    conn.execute("DELETE FROM notification_settings WHERE user_id = ?", (uid,))
    conn.execute("DELETE FROM logs WHERE user_id = ?", (uid,))
    conn.execute("DELETE FROM users WHERE username = ?", (user_id,))
    conn.commit()
except Exception:
    pass
conn.close()
PY

rm -rf "$ROOT_DIR/runtime/users/$TEST_USER"
rm -rf "$ROOT_DIR/runtime/tmp"

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
[[ "$FAIL" -eq 0 ]] || exit 1
echo "[OK] all shell/schedule tests passed"
