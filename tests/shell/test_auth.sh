#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

RUN_ONLINE=false
ONLINE_ACCOUNT=""
ONLINE_PASSWORD=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --online)   RUN_ONLINE=true ;;
    --account)  ONLINE_ACCOUNT="$2"; shift ;;
    --password) ONLINE_PASSWORD="$2"; shift ;;
  esac
  shift
done

PYTHON=""
WIN_PYTHON=false
if [[ -x /usr/bin/python3 ]]; then
  PYTHON=/usr/bin/python3
  echo "[INFO] using WSL python3 for testing"
elif [[ -f "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/.venv/bin/python"
elif [[ -f "$ROOT_DIR/.venv/Scripts/python.exe" ]]; then
  echo "[SKIP] Windows venv detected but incompatible with WSL Bash"
  echo "[INFO] please install python3-cryptography python3-requests in WSL or use PowerShell"
  exit 0
else
  echo "[SKIP] no usable python found"
  exit 0
fi

mkdir -p "$ROOT_DIR/runtime/tmp"
printf '#!/usr/bin/env bash\nexec "%s" "$@"\n' "$PYTHON" > "$ROOT_DIR/runtime/tmp/python"
chmod +x "$ROOT_DIR/runtime/tmp/python"
export PATH="$ROOT_DIR/runtime/tmp:$PATH"

AUTH_DIR="$ROOT_DIR/shell/auth"
CLIENT="$AUTH_DIR/webvpn_client.py"
TEST_USER="test_auth_999"
TEST_DB="$ROOT_DIR/database/campus_pilot.db"

PASS=0; FAIL=0

ok()   { echo "  [PASS] $1"; PASS=$((PASS+1)); }
fail() { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }

assert_contains() {
  [[ "$1" == *"$2"* ]] && ok "$3" || fail "$3 (missing: $2)"
}
assert_not_contains() {
  [[ "$1" != *"$2"* ]] && ok "$3" || fail "$3 (should not contain: $2)"
}
assert_file_exists()     { [[ -f "$1" ]] && ok "$2" || fail "$2 (missing: $1)"; }
assert_file_not_exists() { [[ ! -f "$1" ]] && ok "$2" || fail "$2 (should not exist: $1)"; }

mkdir -p "$ROOT_DIR/database" "$ROOT_DIR/runtime/users/$TEST_USER"

"$PYTHON" - "$TEST_DB" "$TEST_USER" <<'PYEOF'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
conn.executescript("""
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS campus_accounts (
    user_id TEXT PRIMARY KEY,
    campus_account TEXT,
    campus_password_encrypted TEXT,
    webvpn_cookie_path TEXT,
    session_valid INTEGER DEFAULT 0,
    last_login_at TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    session_type TEXT,
    cookie_path TEXT,
    is_valid INTEGER DEFAULT 1,
    last_checked_at TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
""")
conn.execute("DELETE FROM campus_accounts WHERE user_id = ?", (sys.argv[2],))
conn.execute("DELETE FROM sessions WHERE user_id = ?", (sys.argv[2],))
conn.commit()
conn.close()
PYEOF

export DATABASE_PATH="$TEST_DB"

echo ""
echo "=== [1] webvpn_client.py basic validation ==="

usage_out="$("$PYTHON" "$CLIENT" 2>&1 || true)"
assert_contains "$usage_out" "usage" "no-args shows usage"

bad_action="$("$PYTHON" "$CLIENT" badaction "$TEST_USER" 2>&1 || true)"
assert_contains "$bad_action" "invalid choice" "bad action rejected"

echo ""
echo "=== [2] save_credentials.sh ==="

save_out="$(bash "$AUTH_DIR/save_credentials.sh" "$TEST_USER" "testaccount" "testpass123" 2>&1)"
assert_contains     "$save_out" '"success": true'  "save_credentials success"
assert_not_contains "$save_out" '"success": false' "save_credentials no error"

db_row="$("$PYTHON" - "$TEST_DB" "$TEST_USER" <<'PYEOF2'
import sqlite3, json, sys
conn = sqlite3.connect(sys.argv[1])
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT campus_account, campus_password_encrypted FROM campus_accounts WHERE user_id = ?", (sys.argv[2],)).fetchone()
print(json.dumps(dict(row) if row else {}))
PYEOF2
)"
assert_contains     "$db_row" "testaccount" "account saved to db"
assert_not_contains "$db_row" "testpass123" "plain password not in db"

save_out2="$(bash "$AUTH_DIR/save_credentials.sh" "$TEST_USER" "newaccount" "newpass456" 2>&1)"
assert_contains "$save_out2" '"success": true' "save_credentials upsert ok"

db_row2="$("$PYTHON" - "$TEST_DB" "$TEST_USER" <<'PYEOF3'
import sqlite3, json, sys
conn = sqlite3.connect(sys.argv[1])
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT campus_account FROM campus_accounts WHERE user_id = ?", (sys.argv[2],)).fetchone()
print(json.dumps(dict(row) if row else {}))
PYEOF3
)"
assert_contains "$db_row2" "newaccount" "upsert updated account name"

missing_args="$(bash "$AUTH_DIR/save_credentials.sh" 2>&1 || true)"
assert_contains "$missing_args" '"success": false' "save_credentials missing args"

echo ""
echo "=== [3] login_bound.sh error handling ==="

"$PYTHON" - "$TEST_DB" "$TEST_USER" <<'PYEOF4'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
conn.execute("DELETE FROM campus_accounts WHERE user_id = ?", (sys.argv[2],))
conn.commit()
PYEOF4

no_bind="$(bash "$AUTH_DIR/login_bound.sh" "$TEST_USER" 2>&1 || true)"
assert_contains     "$no_bind" '"success": false' "login_bound no bind returns false"
assert_contains     "$no_bind" "campus account"   "login_bound no bind has reason"
assert_not_contains "$no_bind" '"success": true'  "login_bound no bind not true"

no_uid="$(bash "$AUTH_DIR/login_bound.sh" 2>&1 || true)"
assert_contains "$no_uid" '"success": false' "login_bound missing user_id"
assert_contains "$no_uid" "user_id"          "login_bound missing user_id reason"

echo ""
echo "=== [4] check_session.sh error handling ==="

rm -f "$ROOT_DIR/runtime/users/$TEST_USER/webvpn.cookie"
bash "$AUTH_DIR/save_credentials.sh" "$TEST_USER" "testaccount" "testpass" >/dev/null 2>&1

no_cookie="$(bash "$AUTH_DIR/check_session.sh" "$TEST_USER" 2>&1 || true)"
assert_contains     "$no_cookie" '"success": false' "check_session no cookie returns false"
assert_not_contains "$no_cookie" '"success": true'  "check_session no cookie not true"

no_uid_check="$(bash "$AUTH_DIR/check_session.sh" 2>&1 || true)"
assert_contains "$no_uid_check" '"success": false' "check_session missing user_id"

echo ""
echo "=== [5] logout.sh cleanup ==="

mkdir -p "$ROOT_DIR/runtime/users/$TEST_USER"
printf 'FAKE_SESSION=abc123\n' > "$ROOT_DIR/runtime/users/$TEST_USER/webvpn.cookie"

"$PYTHON" - "$TEST_DB" "$TEST_USER" <<'PYEOF5'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
conn.execute("UPDATE campus_accounts SET session_valid=1 WHERE user_id=?", (sys.argv[2],))
conn.commit()
PYEOF5

logout_out="$(bash "$AUTH_DIR/logout.sh" "$TEST_USER" 2>&1 || true)"
assert_contains "$logout_out" '"success"' "logout returns json"

assert_file_not_exists \
  "$ROOT_DIR/runtime/users/$TEST_USER/webvpn.cookie" \
  "logout deletes cookie file"

db_valid="$("$PYTHON" - "$TEST_DB" "$TEST_USER" <<'PYEOF6'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
row = conn.execute("SELECT session_valid FROM campus_accounts WHERE user_id=?", (sys.argv[2],)).fetchone()
print(row[0] if row else "none")
PYEOF6
)"
[[ "$db_valid" == "0" ]] \
  && ok "logout sets session_valid=0" \
  || fail "logout session_valid not 0 (got: $db_valid)"

echo ""
echo "=== [6] refresh_session.sh error handling ==="

"$PYTHON" - "$TEST_DB" "$TEST_USER" <<'PYEOF7'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
conn.execute("DELETE FROM campus_accounts WHERE user_id=?", (sys.argv[2],))
conn.commit()
PYEOF7

no_bind_refresh="$(bash "$AUTH_DIR/refresh_session.sh" "$TEST_USER" 2>&1 || true)"
assert_contains     "$no_bind_refresh" '"success": false' "refresh no bind returns false"
assert_not_contains "$no_bind_refresh" '"success": true'  "refresh no bind not true"

echo ""
echo "=== [7] online test (--online --account <id> --password <pass>) ==="

if [[ "$RUN_ONLINE" == true ]]; then
  if [[ -z "$ONLINE_ACCOUNT" || -z "$ONLINE_PASSWORD" ]]; then
    echo "  [SKIP] --account and --password not provided"
  else
    bash "$AUTH_DIR/save_credentials.sh" "$TEST_USER" "$ONLINE_ACCOUNT" "$ONLINE_PASSWORD" >/dev/null

    login_out="$(bash "$AUTH_DIR/login_bound.sh" "$TEST_USER" 2>&1 || true)"
    echo "  login: $login_out"

    if [[ "$login_out" == *'"success": true'* ]]; then
      ok "online login success"

      assert_file_exists "$ROOT_DIR/runtime/users/$TEST_USER/webvpn.cookie" "cookie file created"

      check_out="$(bash "$AUTH_DIR/check_session.sh" "$TEST_USER" 2>&1)"
      assert_contains "$check_out" '"success": true' "check_session valid after login"

      refresh_out="$(bash "$AUTH_DIR/refresh_session.sh" "$TEST_USER" 2>&1)"
      assert_contains "$refresh_out" '"success": true' "refresh_session valid after login"

      bash "$AUTH_DIR/logout.sh" "$TEST_USER" >/dev/null 2>&1
      after_logout="$(bash "$AUTH_DIR/check_session.sh" "$TEST_USER" 2>&1 || true)"
      assert_contains "$after_logout" '"success": false' "check_session fails after logout"
    else
      fail "online login failed: $login_out"
    fi
  fi
else
  echo "  [skipped] pass --online --account <id> --password <pass> to run"
fi

"$PYTHON" - "$TEST_DB" "$TEST_USER" <<'PYEOF8'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
conn.execute("DELETE FROM campus_accounts WHERE user_id=?", (sys.argv[2],))
conn.execute("DELETE FROM sessions WHERE user_id=?", (sys.argv[2],))
conn.commit()
PYEOF8
rm -rf "$ROOT_DIR/runtime/users/$TEST_USER"
rm -rf "$ROOT_DIR/runtime/tmp"

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
[[ "$FAIL" -eq 0 ]] || exit 1
echo "[OK] all shell/auth tests passed"
