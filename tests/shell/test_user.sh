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

USER_DIR="$ROOT_DIR/shell/user"
TEST_USER="test_ucfg_999"
TEST_DB="$ROOT_DIR/database/campus_pilot.db"
export DATABASE_PATH="$TEST_DB"

PASS=0; FAIL=0
ok()   { echo "  [PASS] $1"; PASS=$((PASS+1)); }
fail() { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }
ac()   { [[ "$1" == *"$2"* ]] && ok "$3" || fail "$3"; }
anc()  { [[ "$1" != *"$2"* ]] && ok "$3" || fail "$3"; }
afe()  { [[ -f "$1" ]] && ok "$2" || fail "$2"; }

echo "=== Setup ==="
"$_PY" - "$TEST_DB" "$TEST_USER" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
c.executescript("""
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE,password_hash TEXT,role TEXT DEFAULT 'user',email TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS notification_settings(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,enable_email INTEGER DEFAULT 0,enable_desktop INTEGER DEFAULT 1,enable_seat_result INTEGER DEFAULT 1,enable_schedule_reminder INTEGER DEFAULT 1,enable_error_alert INTEGER DEFAULT 1,schedule_default_reminders TEXT DEFAULT '[15]',exam_default_reminders TEXT DEFAULT '[1440,120]',task_default_reminders TEXT DEFAULT '[1440,120]',created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id)REFERENCES users(id));
CREATE TABLE IF NOT EXISTS reminders(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,target_type TEXT,target_id INTEGER,remind_before_minutes INTEGER,enabled INTEGER DEFAULT 1,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id)REFERENCES users(id));
CREATE TABLE IF NOT EXISTS seat_configs(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,floor TEXT,seat_no TEXT,priority INTEGER DEFAULT 1,reserve_date TEXT,reserve_start_time TEXT,reserve_end_time TEXT,reserve_time_slots TEXT,check_start_time TEXT,check_stop_time TEXT,retry_interval INTEGER DEFAULT 10,max_retry_count INTEGER DEFAULT 30,max_duration_minutes INTEGER DEFAULT 15,enabled INTEGER DEFAULT 1,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id)REFERENCES users(id));
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,title TEXT,category TEXT,priority TEXT DEFAULT 'medium',deadline TEXT,repeat_rule TEXT,reminder_time TEXT,note TEXT,status TEXT DEFAULT 'pending',created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id)REFERENCES users(id));
CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,module TEXT,level TEXT DEFAULT 'INFO',message TEXT,detail TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id)REFERENCES users(id));
""")
u=sys.argv[2]
c.execute("INSERT OR IGNORE INTO users(username,password_hash)VALUES(?,'h')",(u,))
uid=c.execute("SELECT id FROM users WHERE username=?",(u,)).fetchone()[0]
for t in["notification_settings","reminders","seat_configs","tasks","logs"]:c.execute(f"DELETE FROM {t} WHERE user_id=?",(uid,))
c.execute("INSERT INTO notification_settings(user_id,enable_email)VALUES(?,1)",(uid,))
c.execute("INSERT INTO tasks(user_id,title,deadline,priority,status)VALUES(?,'T1','2026-07-01 10:00','high','pending')",(uid,))
c.execute("INSERT INTO tasks(user_id,title,deadline,priority,status)VALUES(?,'T2','2026-07-02 15:00','low','done')",(uid,))
tid=c.execute("SELECT id FROM tasks WHERE user_id=? LIMIT 1",(uid,)).fetchone()[0]
c.execute("INSERT INTO reminders(user_id,target_type,target_id,remind_before_minutes)VALUES(?,'task',?,30)",(uid,tid))
c.execute("INSERT INTO seat_configs(user_id,seat_no,priority,reserve_date,reserve_start_time,reserve_end_time)VALUES(?,'A101',1,'2026-07-05','08:00','12:00')",(uid,))
c.commit();c.close()
print("ok")
PY

echo ""
echo "=== [1] export basic ==="
out1="$(bash "$USER_DIR/export_config.sh" "$TEST_USER" 2>&1)"
ac "$out1" '"success": true' "export succeeds"
ac "$out1" '"export_path"' "has export_path"
ac "$out1" '"tasks_count": 2' "2 tasks"
ac "$out1" '"reminders_count": 1' "1 reminder"
ac "$out1" '"seat_configs_count": 1' "1 seat cfg"
EPATH="$(echo "$out1"|"$_PY" -c 'import json,sys;d=json.loads(sys.stdin.read());print(d.get("data",{}).get("export_path",""))')"
afe "$EPATH" "export file exists"

echo ""
echo "=== [2] export JSON structure ==="
ejson="$(cat "$EPATH")"
ac "$ejson" '"version"' "has version"
ac "$ejson" '"exported_at"' "has timestamp"
ac "$ejson" '"notification_settings"' "has ns"
ac "$ejson" '"reminders"' "has reminders"
ac "$ejson" '"seat_configs"' "has seat_configs"
ac "$ejson" '"tasks"' "has tasks"
ac "$ejson" '"T1"' "task data"
ac "$ejson" '"A101"' "seat data"

echo ""
echo "=== [3] no sensitive data ==="
anc "$ejson" '"user_id"' "no user_id"
anc "$ejson" 'password' "no password"
anc "$ejson" 'token' "no token"
anc "$ejson" 'cookie' "no cookie"

echo ""
echo "=== [4] export errors ==="
e1="$(bash "$USER_DIR/export_config.sh" 2>&1||true)"
ac "$e1" '"success": false' "fails no args"
ac "$e1" "user_id is required" "correct error"
e2="$(bash "$USER_DIR/export_config.sh" "ghost999" 2>&1||true)"
ac "$e2" '"success": false' "fails bad user"
ac "$e2" "user not found" "correct msg"

echo ""
echo "=== [5] custom path ==="
CPATH="$ROOT_DIR/runtime/tmp/my.json"
out2="$(bash "$USER_DIR/export_config.sh" "$TEST_USER" "$CPATH" 2>&1)"
ac "$out2" '"success": true' "custom path ok"
afe "$CPATH" "custom file exists"
ac "$out2" "my.json" "path in response"

echo ""
echo "=== [6] import basic ==="
"$_PY" - "$TEST_DB" "$TEST_USER" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1])
uid=c.execute("SELECT id FROM users WHERE username=?",(sys.argv[2],)).fetchone()[0]
for t in["tasks","reminders","seat_configs"]:c.execute(f"DELETE FROM {t} WHERE user_id=?",(uid,))
c.commit();c.close()
PY
out3="$(bash "$USER_DIR/import_config.sh" "$TEST_USER" "$EPATH" 2>&1)"
ac "$out3" '"success": true' "import ok"
ac "$out3" '"notification_settings": 1' "ns imported"
ac "$out3" '"tasks": 2' "2 tasks imported"
ac "$out3" '"reminders": 1' "1 reminder imported"
ac "$out3" '"seat_configs": 1' "1 seat imported"

echo ""
echo "=== [7] verify DB ==="
chk="$("$_PY" - "$TEST_DB" "$TEST_USER" <<'PY'
import sqlite3,json,sys
c=sqlite3.connect(sys.argv[1]);c.row_factory=sqlite3.Row
uid=c.execute("SELECT id FROM users WHERE username=?",(sys.argv[2],)).fetchone()[0]
ts=[dict(r)for r in c.execute("SELECT title,priority FROM tasks WHERE user_id=?",(uid,))]
sc=[dict(r)for r in c.execute("SELECT seat_no FROM seat_configs WHERE user_id=?",(uid,))]
rm=[dict(r)for r in c.execute("SELECT target_type FROM reminders WHERE user_id=?",(uid,))]
print(json.dumps({"tasks":ts,"seats":sc,"reminders":rm}))
PY
)"
ac "$chk" '"T1"' "T1 in db"
ac "$chk" '"T2"' "T2 in db"
ac "$chk" '"A101"' "A101 in db"
ac "$chk" '"task"' "reminder in db"

echo ""
echo "=== [8] import errors ==="
e3="$(bash "$USER_DIR/import_config.sh" 2>&1||true)"
ac "$e3" '"success": false' "fails no args"
ac "$e3" "user_id and import_path are required" "correct msg"
e4="$(bash "$USER_DIR/import_config.sh" "$TEST_USER" "/tmp/nofile999.json" 2>&1||true)"
ac "$e4" '"success": false' "fails missing file"
ac "$e4" "import file not found" "correct msg"
echo "{bad}" > "$ROOT_DIR/runtime/tmp/bad.json"
e5="$(bash "$USER_DIR/import_config.sh" "$TEST_USER" "$ROOT_DIR/runtime/tmp/bad.json" 2>&1||true)"
ac "$e5" '"success": false' "fails bad json"

echo ""
echo "=== [9] round-trip ==="
"$_PY" - "$TEST_DB" "$TEST_USER" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1])
uid=c.execute("SELECT id FROM users WHERE username=?",(sys.argv[2],)).fetchone()[0]
for t in["tasks","reminders","seat_configs"]:c.execute(f"DELETE FROM {t} WHERE user_id=?",(uid,))
c.commit();c.close()
PY
bash "$USER_DIR/import_config.sh" "$TEST_USER" "$CPATH" >/dev/null 2>&1
out4="$(bash "$USER_DIR/export_config.sh" "$TEST_USER" 2>&1)"
ac "$out4" '"tasks_count": 2' "rt:2 tasks"
ac "$out4" '"seat_configs_count": 1' "rt:1 seat"
ac "$out4" '"reminders_count": 1' "rt:1 reminder"

echo ""
echo "=== Cleanup ==="
"$_PY" - "$TEST_DB" "$TEST_USER" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1])
try:
  uid=c.execute("SELECT id FROM users WHERE username=?",(sys.argv[2],)).fetchone()[0]
  for t in["notification_settings","reminders","seat_configs","tasks","logs"]:c.execute(f"DELETE FROM {t} WHERE user_id=?",(uid,))
  c.execute("DELETE FROM users WHERE username=?",(sys.argv[2],))
  c.commit()
except:pass
c.close()
PY
rm -rf "$ROOT_DIR/runtime/users/$TEST_USER" "$ROOT_DIR/runtime/tmp"

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
[[ "$FAIL" -eq 0 ]] || exit 1
echo "[OK] all shell/user tests passed"
