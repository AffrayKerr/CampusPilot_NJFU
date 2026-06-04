#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# 是否跑网络测试（默认跳过，传 --online 开启）
RUN_NETWORK=false
for arg in "$@"; do
  [[ "$arg" == "--online" ]] && RUN_NETWORK=true
done

# 找可用的 Python（优先 /usr/bin/python3 避免 conda 劫持，只检查文件存在不执行）
_PYTHON_CMD=""
for _c in /usr/bin/python3 /usr/local/bin/python3; do
  if [[ -x "$_c" ]]; then
    _PYTHON_CMD="$_c"
    break
  fi
done
if [[ -z "$_PYTHON_CMD" ]]; then
  echo "[SKIP] no usable python found"
  exit 0
fi

# 创建 python wrapper 让 common/*.sh 里的裸 `python` 命令生效
mkdir -p "$ROOT_DIR/runtime/tmp"
printf '#!/usr/bin/env bash\nexec "%s" "$@"\n' "$_PYTHON_CMD" \
  > "$ROOT_DIR/runtime/tmp/python"
chmod +x "$ROOT_DIR/runtime/tmp/python"
export PATH="$ROOT_DIR/runtime/tmp:$PATH"

source shell/common/env.sh
source shell/common/response.sh
source shell/common/db.sh
source shell/common/cookie.sh
source shell/common/log.sh
source shell/common/network.sh

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

assert_file_exists()    { [[ -f "$1" ]] && ok "$2" || fail "$2 (missing: $1)"; }
assert_file_not_exists(){ [[ ! -f "$1" ]] && ok "$2" || fail "$2 (should not exist: $1)"; }
assert_dir_exists()     { [[ -d "$1" ]] && ok "$2" || fail "$2 (missing dir: $1)"; }

# ────────────────────────────────────────────────────────────────────────────
echo ""
echo "=== [1/6] env ==="

[[ -n "${PROJECT_ROOT:-}" ]] && ok "PROJECT_ROOT set" || fail "PROJECT_ROOT empty"
[[ -n "${DATABASE_PATH:-}" ]] && ok "DATABASE_PATH set" || fail "DATABASE_PATH empty"
[[ -n "${LOG_DIR:-}" ]]       && ok "LOG_DIR set"       || fail "LOG_DIR empty"
[[ -n "${RUNTIME_DIR:-}" ]]   && ok "RUNTIME_DIR set"   || fail "RUNTIME_DIR empty"

user_dir="$(shell_env_ensure_user_runtime_dir "_testuser")"
assert_dir_exists "$user_dir" "user runtime dir created"

# ────────────────────────────────────────────────────────────────────────────
echo ""
echo "=== [2/6] response ==="

r_ok="$(shell_response_json true "执行成功" "{}")"
assert_contains "$r_ok" '"success": true'    "success=true flag"
assert_contains "$r_ok" '"message": "执行成功"' "message field"
assert_contains "$r_ok" '"data":'             "data key present"

r_fail="$(shell_response_json false "出错了" "null")"
assert_contains     "$r_fail" '"success": false' "success=false flag"
assert_not_contains "$r_fail" '"success": true'  "no true in failure"

r_data="$(shell_response_json true "ok" '{"key":"val"}')"
assert_contains "$r_data" '"key"'   "data object passthrough"
assert_contains "$r_data" '"val"'   "data object value passthrough"

# ────────────────────────────────────────────────────────────────────────────
echo ""
echo "=== [3/6] db ==="

shell_db_init
shell_db_execute "CREATE TABLE IF NOT EXISTS _test_tbl(id INTEGER PRIMARY KEY, name TEXT)"
shell_db_execute "DELETE FROM _test_tbl"

shell_db_execute "INSERT INTO _test_tbl(name) VALUES (?)" "alice"
shell_db_execute "INSERT INTO _test_tbl(name) VALUES (?)" "bob"

rows="$(shell_db_query "SELECT name FROM _test_tbl ORDER BY id")"
assert_contains "$rows" "alice" "insert+query alice"
assert_contains "$rows" "bob"   "insert+query bob"

shell_db_execute "DELETE FROM _test_tbl WHERE name = ?" "alice"
rows2="$(shell_db_query "SELECT name FROM _test_tbl")"
assert_not_contains "$rows2" "alice" "delete alice"
assert_contains     "$rows2" "bob"   "bob still exists"

shell_db_execute "DROP TABLE _test_tbl"
ok "drop table"

# ────────────────────────────────────────────────────────────────────────────
echo ""
echo "=== [4/6] cookie ==="

shell_cookie_delete "_testuser" 2>/dev/null || true
assert_file_not_exists "$(shell_cookie_path "_testuser")" "no cookie before save"

# cookie_read 应返回非零退出码
if shell_cookie_read "_testuser" 2>/dev/null; then
  fail "cookie_read on missing file should return non-zero"
else
  ok "cookie_read missing → non-zero exit"
fi

cookie_file="$(shell_cookie_save "_testuser" "SESSION=xyz789")"
assert_file_exists "$cookie_file" "cookie file created"

val="$(shell_cookie_read "_testuser")"
assert_contains "$val" "SESSION=xyz789" "cookie read value"

shell_cookie_delete "_testuser"
assert_file_not_exists "$cookie_file" "cookie file deleted"

if shell_cookie_read "_testuser" 2>/dev/null; then
  fail "cookie_read after delete should return non-zero"
else
  ok "cookie_read after delete → non-zero exit"
fi

# ────────────────────────────────────────────────────────────────────────────
echo ""
echo "=== [5/6] log ==="

rm -f "runtime/users/_testuser/runtime.log"
shell_log_write INFO auth "test message" "some detail" "_testuser"
assert_file_exists "runtime/users/_testuser/runtime.log" "user log file created"

log_content="$(cat runtime/users/_testuser/runtime.log)"
assert_contains "$log_content" '"timestamp"'             "log has timestamp"
assert_contains "$log_content" '"level": "INFO"'         "log level INFO"
assert_contains "$log_content" '"module": "auth"'        "log module auth"
assert_contains "$log_content" '"message": "test message"' "log message"
assert_contains "$log_content" '"detail": "some detail"' "log detail"

rm -f "logs/system.log"
shell_log_write WARNING system "sys warn" "" ""
assert_file_exists "logs/system.log" "system log file created"
sys_log="$(cat logs/system.log)"
assert_contains "$sys_log" '"level": "WARNING"' "system log level WARNING"
assert_contains "$sys_log" '"timestamp"'        "system log has timestamp"

# ────────────────────────────────────────────────────────────────────────────
echo ""
echo "=== [6/6] network (offline checks only) ==="

# 函数必须存在（可调用），不在意返回值
if declare -f shell_network_is_available >/dev/null 2>&1; then
  ok "shell_network_is_available function exists"
else
  fail "shell_network_is_available not defined"
fi

if declare -f shell_network_check_vpn >/dev/null 2>&1; then
  ok "shell_network_check_vpn function exists"
else
  fail "shell_network_check_vpn not defined"
fi

if declare -f shell_network_request_with_cookie >/dev/null 2>&1; then
  ok "shell_network_request_with_cookie function exists"
else
  fail "shell_network_request_with_cookie not defined"
fi

# 在线测试（传 --online 才执行）
if [[ "$RUN_NETWORK" == true ]]; then
  echo "  [running online checks...]"
  net="$(shell_network_is_available "https://www.baidu.com")"
  [[ "$net" == "true" || "$net" == "false" ]] \
    && ok "network_is_available output valid" \
    || fail "network_is_available bad output: $net"

  vpn="$(shell_network_check_vpn)"
  [[ "$vpn" == "true" || "$vpn" == "false" ]] \
    && ok "network_check_vpn output valid" \
    || fail "network_check_vpn bad output: $vpn"

  code="$(shell_network_request_with_cookie "https://www.baidu.com" "")"
  [[ "$code" =~ ^[0-9]+$ && "$code" -ge 0 && "$code" -lt 600 ]] \
    && ok "request_with_cookie returns http status" \
    || fail "request_with_cookie bad output: $code"
else
  echo "  [skipped — pass --online to run network tests]"
fi

# ────────────────────────────────────────────────────────────────────────────
rm -rf "$ROOT_DIR/runtime/tmp"
rm -rf "$ROOT_DIR/runtime/users/_testuser"

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
[[ "$FAIL" -eq 0 ]] || exit 1
echo "[OK] all shell/common tests passed"
