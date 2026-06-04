#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

source shell/common/env.sh
source shell/common/response.sh
source shell/common/db.sh
source shell/common/cookie.sh
source shell/common/log.sh
source shell/common/network.sh

fail() {
  echo "[FAIL] $1"
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "expected to contain: $needle"
}

echo "[1/6] test env"
[[ -n "${PROJECT_ROOT:-}" ]] || fail "PROJECT_ROOT is empty"
[[ -n "${DATABASE_PATH:-}" ]] || fail "DATABASE_PATH is empty"
user_dir="$(shell_env_ensure_user_runtime_dir 1)"
[[ -d "$user_dir" ]] || fail "user runtime dir not created"

echo "[2/6] test response"
response_json="$(shell_response_json true "执行成功" "{}")"
assert_contains "$response_json" '"success": true'
assert_contains "$response_json" '"message": "执行成功"'

echo "[3/6] test db"
shell_db_init
shell_db_execute "CREATE TABLE IF NOT EXISTS test_common(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)"
shell_db_execute "DELETE FROM test_common"
shell_db_execute "INSERT INTO test_common(name) VALUES (?)" "hello"
rows_json="$(shell_db_query "SELECT name FROM test_common")"
assert_contains "$rows_json" 'hello'

echo "[4/6] test cookie"
cookie_file="$(shell_cookie_save 1 "cookie=value123")"
[[ -f "$cookie_file" ]] || fail "cookie file not created"
cookie_value="$(shell_cookie_read 1)"
assert_contains "$cookie_value" 'cookie=value123'
shell_cookie_delete 1
[[ ! -f "$cookie_file" ]] || fail "cookie file not deleted"

echo "[5/6] test log"
shell_log_write INFO system "hello" "detail" 1
[[ -f "runtime/users/1/runtime.log" ]] || fail "runtime log not created"
log_content="$(cat runtime/users/1/runtime.log)"
assert_contains "$log_content" '"message": "hello"'

echo "[6/6] test network"
network_result="$(shell_network_is_available https://www.baidu.com)"
[[ "$network_result" == "true" || "$network_result" == "false" ]] || fail "unexpected network result"

echo "[OK] common shell modules pass smoke test"
