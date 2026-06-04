#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../common/env.sh
source "$SCRIPT_DIR/../common/env.sh"
# shellcheck source=../common/response.sh
source "$SCRIPT_DIR/../common/response.sh"
# shellcheck source=../common/log.sh
source "$SCRIPT_DIR/../common/log.sh"
# shellcheck source=../common/db.sh
source "$SCRIPT_DIR/../common/db.sh"
# shellcheck source=../common/cookie.sh
source "$SCRIPT_DIR/../common/cookie.sh"

user_id="${1:-}"
if [[ -z "$user_id" ]]; then
  shell_response_json false "user_id is required" null
  exit 1
fi

shell_db_init
cookie_file="$(shell_cookie_path "$user_id")"
if [[ ! -f "$cookie_file" ]]; then
  shell_db_execute "UPDATE campus_accounts SET session_valid = 0, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?" "$user_id"
  shell_log_write WARNING auth "webvpn session invalid: cookie missing" "user_id=$user_id" "$user_id"
  shell_response_json false "session cookie not found" null
  exit 1
fi

check_result="$(python - "$cookie_file" <<'PY'
import json
import sys
from pathlib import Path

try:
    import requests
except Exception as exc:
    print(json.dumps({"success": False, "message": f"requests unavailable: {exc}", "data": None}, ensure_ascii=False))
    raise SystemExit(1)

cookie_file = Path(sys.argv[1])
session = requests.Session()
with cookie_file.open('r', encoding='utf-8') as fh:
    for line in fh:
        line = line.strip()
        if not line or '=' not in line:
            continue
        name, value = line.split('=', 1)
        session.cookies.set(name, value)

url = 'https://vpn.nijfu.edu.cn/'
try:
    resp = session.get(url, timeout=20, verify=False, allow_redirects=True)
    ok = resp.status_code < 400 and '统一身份认证' not in resp.text
    print(json.dumps({"success": ok, "message": "执行成功" if ok else "session expired", "data": {"status_code": resp.status_code, "final_url": resp.url}}, ensure_ascii=False))
except Exception as exc:
    print(json.dumps({"success": False, "message": f"session check failed: {exc}", "data": None}, ensure_ascii=False))
    raise SystemExit(1)
PY
)"

check_success="$(python - "$check_result" <<'PY'
import json, sys
obj = json.loads(sys.argv[1])
print('true' if obj.get('success') else 'false')
PY
)"

if [[ "$check_success" != "true" ]]; then
  shell_db_execute "UPDATE campus_accounts SET session_valid = 0, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?" "$user_id"
  shell_log_write WARNING auth "webvpn session invalid" "user_id=$user_id result=$check_result" "$user_id"
  shell_response_json false "session invalid" "$check_result"
  exit 1
fi

shell_db_execute "UPDATE campus_accounts SET session_valid = 1, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?" "$user_id"
shell_log_write INFO auth "webvpn session checked" "user_id=$user_id cookie=$cookie_file" "$user_id"

result_json="$(shell_db_query "SELECT session_valid, webvpn_cookie_path, last_login_at FROM campus_accounts WHERE user_id = ?" "$user_id")"
shell_response_json true "执行成功" "$result_json"
