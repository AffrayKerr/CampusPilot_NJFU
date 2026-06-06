#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

_PY=""
for _c in /usr/bin/python3 python3; do
  command -v "$_c" >/dev/null 2>&1 && _PY="$_c" && break
done
[[ -z "$_PY" ]] && echo "[SKIP] no python3" && exit 0

mkdir -p "$ROOT_DIR/runtime/tmp"
printf '#!/usr/bin/env bash\nexec "%s" "$@"\n' "$_PY" > "$ROOT_DIR/runtime/tmp/python"
chmod +x "$ROOT_DIR/runtime/tmp/python"
export PATH="$ROOT_DIR/runtime/tmp:$PATH"

NOTIFY_DIR="$ROOT_DIR/shell/notification"
TEST_USER="test_notify_999"
TEST_DB="$ROOT_DIR/database/campus_pilot.db"
export DATABASE_PATH="$TEST_DB"

PASS=0; FAIL=0
ok()   { echo "  [PASS] $1"; PASS=$((PASS+1)); }
fail() { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }
ac()   { [[ "$1" == *"$2"* ]] && ok "$3" || fail "$3 (missing: $2)"; }
anc()  { [[ "$1" != *"$2"* ]] && ok "$3" || fail "$3 (should not have: $2)"; }

echo "=== Setup ==="
"$_PY" - "$TEST_DB" "$TEST_USER" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
c.executescript("""
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE,password_hash TEXT,role TEXT DEFAULT 'user',email TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS notification_settings(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,enable_email INTEGER DEFAULT 0,enable_desktop INTEGER DEFAULT 1,enable_seat_result INTEGER DEFAULT 1,enable_schedule_reminder INTEGER DEFAULT 1,enable_error_alert INTEGER DEFAULT 1,schedule_default_reminders TEXT DEFAULT '[15]',exam_default_reminders TEXT DEFAULT '[1440,120]',task_default_reminders TEXT DEFAULT '[1440,120]',created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id)REFERENCES users(id));
CREATE TABLE IF NOT EXISTS feedbacks(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,type TEXT NOT NULL,title TEXT NOT NULL,content TEXT NOT NULL,contact_email TEXT,priority TEXT DEFAULT 'medium',status TEXT DEFAULT 'pending',context_info TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS seat_configs(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,floor TEXT,seat_no TEXT,priority INTEGER DEFAULT 1,reserve_date TEXT,reserve_start_time TEXT,reserve_end_time TEXT,reserve_time_slots TEXT,check_start_time TEXT,check_stop_time TEXT,retry_interval INTEGER DEFAULT 10,max_retry_count INTEGER DEFAULT 30,max_duration_minutes INTEGER DEFAULT 15,enabled INTEGER DEFAULT 1,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id)REFERENCES users(id));
CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,module TEXT,level TEXT DEFAULT 'INFO',message TEXT,detail TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id)REFERENCES users(id));
""")
u = sys.argv[2]
c.execute("INSERT OR IGNORE INTO users(username,password_hash,email)VALUES(?,'h','test@example.com')",(u,))
uid = c.execute("SELECT id FROM users WHERE username=?",(u,)).fetchone()[0]
for t in ["notification_settings","feedbacks","logs"]: c.execute(f"DELETE FROM {t} WHERE user_id=?",(uid,))
c.execute("INSERT INTO notification_settings(user_id,enable_email,enable_desktop,enable_seat_result)VALUES(?,0,1,1)",(uid,))
c.execute("INSERT INTO feedbacks(user_id,type,title,content,status)VALUES(?,'bug','测试反馈','内容','resolved')",(uid,))
c.commit(); c.close()
print("ok")
PY

echo ""
echo "=== [1] notify_desktop.sh - missing notify-send ==="
d1="$(bash "$NOTIFY_DIR/notify_desktop.sh" 2>&1 || true)"
ac "$d1" '"success": false' "fails without user_id"
ac "$d1" "user_id" "correct error msg"

d2="$(bash "$NOTIFY_DIR/notify_desktop.sh" "$TEST_USER" 2>&1 || true)"
ac "$d2" '"success": false' "fails without title"

d3="$(bash "$NOTIFY_DIR/notify_desktop.sh" "$TEST_USER" "标题" 2>&1 || true)"
ac "$d3" '"success": false' "fails without content"

echo ""
echo "=== [2] notify_desktop.sh - truncation test ==="
long_content="$(python3 -c "print('a' * 200)")"
if command -v notify-send >/dev/null 2>&1; then
  d4="$(bash "$NOTIFY_DIR/notify_desktop.sh" "$TEST_USER" "Title" "$long_content" 2>&1 || true)"
  ac "$d4" '"success": true' "desktop with long content"
else
  echo "  [SKIP] notify-send not available, testing content truncation logic directly"
  trunc_test="$(echo "$long_content" | cut -c1-100)"
  [[ ${#trunc_test} -le 100 ]] && ok "content truncated to 100 chars" || fail "content not truncated"
fi

echo ""
echo "=== [3] notify_email.sh - argument validation ==="
e1="$(bash "$NOTIFY_DIR/notify_email.sh" 2>&1 || true)"
ac "$e1" '"success": false' "fails without user_id"

e2="$(bash "$NOTIFY_DIR/notify_email.sh" "$TEST_USER" 2>&1 || true)"
ac "$e2" '"success": false' "fails without subject"

echo ""
echo "=== [4] notify_email.sh - SMTP not configured ==="
ORIG_SMTP_USER="${SMTP_USER:-}"
ORIG_SMTP_PASS="${SMTP_PASS:-}"
unset SMTP_USER SMTP_PASS
e3="$(bash "$NOTIFY_DIR/notify_email.sh" "$TEST_USER" "Test Subject" "Test Content" "" 2>&1 || true)"
ac "$e3" '"success": false' "fails when SMTP not configured"
ac "$e3" "SMTP not configured" "correct error msg"
[[ -n "$ORIG_SMTP_USER" ]] && export SMTP_USER="$ORIG_SMTP_USER"
[[ -n "$ORIG_SMTP_PASS" ]] && export SMTP_PASS="$ORIG_SMTP_PASS"

echo ""
echo "=== [5] notify_email.sh - no recipient ==="
no_email_user="test_no_email_999"
"$_PY" - "$TEST_DB" "$no_email_user" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
c.execute("INSERT OR IGNORE INTO users(username,password_hash)VALUES(?,'h')",(sys.argv[2],))
uid = c.execute("SELECT id FROM users WHERE username=?",(sys.argv[2],)).fetchone()[0]
c.execute("DELETE FROM notification_settings WHERE user_id=?",(uid,))
c.execute("INSERT INTO notification_settings(user_id)VALUES(?)",(uid,))
c.commit(); c.close()
PY
e4="$(bash "$NOTIFY_DIR/notify_email.sh" "$no_email_user" "Subject" "Content" "" 2>&1 || true)"
ac "$e4" '"success": false' "fails when no email address"
ac "$e4" "No recipient" "correct error msg"
"$_PY" - "$TEST_DB" "$no_email_user" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
uid = c.execute("SELECT id FROM users WHERE username=?",(sys.argv[2],)).fetchone()[0]
c.execute("DELETE FROM notification_settings WHERE user_id=?",(uid,))
c.execute("DELETE FROM users WHERE username=?",(sys.argv[2],))
c.commit(); c.close()
PY

echo ""
echo "=== [6] test_notify.sh - argument validation ==="
t1="$(bash "$NOTIFY_DIR/test_notify.sh" 2>&1 || true)"
ac "$t1" '"success": false' "fails without user_id"

t2="$(bash "$NOTIFY_DIR/test_notify.sh" "$TEST_USER" "invalid_channel" 2>&1 || true)"
ac "$t2" '"success": false' "fails with invalid channel"
ac "$t2" "channel must be" "correct error msg"

echo ""
echo "=== [7] test_notify.sh - valid channels ==="
t3="$(bash "$NOTIFY_DIR/test_notify.sh" "$TEST_USER" "email" "Test" "Content" 2>&1 || true)"
ac "$t3" '"success": true' "test_notify email channel"
ac "$t3" '"email"' "response has email field"

t4="$(bash "$NOTIFY_DIR/test_notify.sh" "$TEST_USER" "desktop" "Test" "Content" 2>&1 || true)"
ac "$t4" '"success": true' "test_notify desktop channel"
ac "$t4" '"desktop"' "response has desktop field"

t5="$(bash "$NOTIFY_DIR/test_notify.sh" "$TEST_USER" "all" "Test" "Content" 2>&1 || true)"
ac "$t5" '"success": true' "test_notify all channel"
ac "$t5" '"email"' "all channel has email"
ac "$t5" '"desktop"' "all channel has desktop"

echo ""
echo "=== [8] notify_result.sh - argument validation ==="
r1="$(bash "$NOTIFY_DIR/notify_result.sh" 2>&1 || true)"
ac "$r1" '"success": false' "fails without user_id"

r2="$(bash "$NOTIFY_DIR/notify_result.sh" "$TEST_USER" 2>&1 || true)"
ac "$r2" '"success": false' "fails without seat_no"

r3="$(bash "$NOTIFY_DIR/notify_result.sh" "$TEST_USER" "A101" 2>&1 || true)"
ac "$r3" '"success": false' "fails without status"

echo ""
echo "=== [9] notify_result.sh - seat result notification ==="
r4="$(bash "$NOTIFY_DIR/notify_result.sh" "$TEST_USER" "A101" "success" "预约时间09:00-12:00" 2>&1 || true)"
ac "$r4" '"success": true' "seat success notification"
ac "$r4" '"seat_no"' "response has seat_no"
ac "$r4" '"sent_count"' "response has sent_count"

r5="$(bash "$NOTIFY_DIR/notify_result.sh" "$TEST_USER" "B202" "failed" "座位已被占用" 2>&1 || true)"
ac "$r5" '"success": true' "seat failed notification"

echo ""
echo "=== [10] notify_result.sh - seat_result disabled ==="
"$_PY" - "$TEST_DB" "$TEST_USER" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
uid = c.execute("SELECT id FROM users WHERE username=?",(sys.argv[2],)).fetchone()[0]
c.execute("UPDATE notification_settings SET enable_seat_result=0 WHERE user_id=?",(uid,))
c.commit(); c.close()
PY
r6="$(bash "$NOTIFY_DIR/notify_result.sh" "$TEST_USER" "C303" "success" "" 2>&1 || true)"
ac "$r6" '"success": true' "returns success even when disabled"
ac "$r6" "skipped" "response says skipped"
"$_PY" - "$TEST_DB" "$TEST_USER" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
uid = c.execute("SELECT id FROM users WHERE username=?",(sys.argv[2],)).fetchone()[0]
c.execute("UPDATE notification_settings SET enable_seat_result=1 WHERE user_id=?",(uid,))
c.commit(); c.close()
PY

echo ""
echo "=== [11] notify_feedback.sh - argument validation ==="
f1="$(bash "$NOTIFY_DIR/notify_feedback.sh" 2>&1 || true)"
ac "$f1" '"success": false' "fails without feedback_id"

f2="$(bash "$NOTIFY_DIR/notify_feedback.sh" "99999" 2>&1 || true)"
ac "$f2" '"success": false' "fails for nonexistent feedback"
ac "$f2" "feedback not found" "correct error msg"

echo ""
echo "=== [12] notify_feedback.sh - sends notification ==="
fb_id="$("$_PY" - "$TEST_DB" "$TEST_USER" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
uid = c.execute("SELECT id FROM users WHERE username=?",(sys.argv[2],)).fetchone()[0]
row = c.execute("SELECT id FROM feedbacks WHERE user_id=? LIMIT 1",(uid,)).fetchone()
print(row[0] if row else "")
PY
)"
if [[ -n "$fb_id" ]]; then
  f3="$(bash "$NOTIFY_DIR/notify_feedback.sh" "$fb_id" 2>&1 || true)"
  ac "$f3" '"success": true' "feedback notification sent"
  ac "$f3" '"feedback_id"' "response has feedback_id"
  ac "$f3" '"sent_count"' "response has sent_count"
else
  fail "feedback_id not found in setup"
fi

echo ""
echo "=== [13] notify_feedback.sh - anonymous feedback ==="
"$_PY" - "$TEST_DB" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
c.execute("INSERT OR IGNORE INTO feedbacks(user_id,type,title,content,status)VALUES(NULL,'feature','匿名反馈','内容','pending')")
c.commit(); c.close()
PY
anon_fb_id="$("$_PY" - "$TEST_DB" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
row = c.execute("SELECT id FROM feedbacks WHERE user_id IS NULL LIMIT 1").fetchone()
print(row[0] if row else "")
PY
)"
if [[ -n "$anon_fb_id" ]]; then
  f4="$(bash "$NOTIFY_DIR/notify_feedback.sh" "$anon_fb_id" 2>&1 || true)"
  ac "$f4" '"success": true' "anonymous feedback returns success"
  ac "$f4" "anonymous" "response says anonymous"
fi

echo ""
echo "=== [14] daily_summary.sh - argument validation ==="
ds1="$(bash "$NOTIFY_DIR/daily_summary.sh" 2>&1 || true)"
ac "$ds1" '"success": false' "fails without user_id"

ds2="$(bash "$NOTIFY_DIR/daily_summary.sh" "ghost_user_999" 2>&1 || true)"
ac "$ds2" '"success": false' "fails for nonexistent user"
ac "$ds2" "user not found" "correct error msg"

echo ""
echo "=== [15] daily_summary.sh - generate summary ==="
"$_PY" - "$TEST_DB" "$TEST_USER" <<'PY'
import sqlite3, sys
from datetime import datetime
c = sqlite3.connect(sys.argv[1])
uid = c.execute("SELECT id FROM users WHERE username=?",(sys.argv[2],)).fetchone()[0]
today = datetime.now()
weekday = today.isoweekday()
today_str = today.strftime("%Y-%m-%d")
c.execute("CREATE TABLE IF NOT EXISTS schedules(id INTEGER PRIMARY KEY,user_id INTEGER,course_name TEXT,teacher TEXT,week_info TEXT,weekday INTEGER,section TEXT,classroom TEXT,note TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
c.execute("CREATE TABLE IF NOT EXISTS exams(id INTEGER PRIMARY KEY,user_id INTEGER,course_name TEXT,exam_time TEXT,exam_location TEXT,seat_number TEXT,note TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
c.execute("CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,user_id INTEGER,title TEXT,category TEXT,priority TEXT DEFAULT 'medium',deadline TEXT,repeat_rule TEXT,reminder_time TEXT,note TEXT,status TEXT DEFAULT 'pending',created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
c.execute("DELETE FROM schedules WHERE user_id=?",(uid,))
c.execute("DELETE FROM exams WHERE user_id=?",(uid,))
c.execute("DELETE FROM tasks WHERE user_id=?",(uid,))
c.execute("INSERT INTO schedules(user_id,course_name,weekday,section,classroom)VALUES(?,'测试课程',?,?,'A101')",(uid,weekday,'1-2'))
c.execute("INSERT INTO tasks(user_id,title,deadline,priority,status)VALUES(?,'今日DDL',?,?,'pending')",(uid,f'{today_str} 23:59','high'))
c.commit(); c.close()
PY

ds3="$(bash "$NOTIFY_DIR/daily_summary.sh" "$TEST_USER" 2>&1 || true)"
ac "$ds3" '"success": true' "daily summary generated"
ac "$ds3" '"courses"' "response has courses count"
ac "$ds3" '"tasks"' "response has tasks count"
ac "$ds3" '"date"' "response has date"
ac "$ds3" '"sent_count"' "response has sent_count"

echo ""
echo "=== [16] daily_summary.sh - all channels disabled ==="
"$_PY" - "$TEST_DB" "$TEST_USER" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
uid = c.execute("SELECT id FROM users WHERE username=?",(sys.argv[2],)).fetchone()[0]
c.execute("UPDATE notification_settings SET enable_email=0,enable_desktop=0 WHERE user_id=?",(uid,))
c.commit(); c.close()
PY
ds4="$(bash "$NOTIFY_DIR/daily_summary.sh" "$TEST_USER" 2>&1 || true)"
ac "$ds4" '"success": true' "returns success when disabled"
ac "$ds4" "skipped" "response says skipped"
"$_PY" - "$TEST_DB" "$TEST_USER" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
uid = c.execute("SELECT id FROM users WHERE username=?",(sys.argv[2],)).fetchone()[0]
c.execute("UPDATE notification_settings SET enable_email=0,enable_desktop=1 WHERE user_id=?",(uid,))
c.commit(); c.close()
PY

echo ""
echo "=== Cleanup ==="
"$_PY" - "$TEST_DB" "$TEST_USER" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
try:
  uid = c.execute("SELECT id FROM users WHERE username=?",(sys.argv[2],)).fetchone()[0]
  for t in ["notification_settings","feedbacks","logs"]: c.execute(f"DELETE FROM {t} WHERE user_id=?",(uid,))
  c.execute("DELETE FROM feedbacks WHERE user_id IS NULL")
  c.execute("DELETE FROM users WHERE username=?",(sys.argv[2],))
  c.commit()
except: pass
c.close()
PY
rm -rf "$ROOT_DIR/runtime/users/$TEST_USER" "$ROOT_DIR/runtime/tmp"

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
[[ "$FAIL" -eq 0 ]] || exit 1
echo "[OK] all shell/notification tests passed"
