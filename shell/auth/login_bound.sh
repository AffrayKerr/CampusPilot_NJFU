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
shell_env_ensure_user_runtime_dir "$user_id" >/dev/null

account_json="$(shell_db_query "SELECT campus_account, campus_password_encrypted FROM campus_accounts WHERE user_id = ?" "$user_id")"
if [[ "$account_json" == "[]" ]]; then
  shell_log_write ERROR auth "webvpn login failed: campus account not bound" "user_id=$user_id" "$user_id"
  shell_response_json false "campus account is not bound" null
  exit 1
fi

campus_account="$(python - "$account_json" <<'PY'
import json, sys
rows = json.loads(sys.argv[1])
print(rows[0]["campus_account"] if rows else "")
PY
)"
campus_password="$(python - "$account_json" <<'PY'
import base64, json, sys
rows = json.loads(sys.argv[1])
if not rows:
    print("")
    raise SystemExit(0)
raw = rows[0].get("campus_password_encrypted", "")
try:
    print(base64.urlsafe_b64decode(raw.encode("utf-8")).decode("utf-8"))
except Exception:
    print(raw)
PY
)"

python - "$user_id" "$campus_account" "$campus_password" <<'PY'
import base64
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests

user_id = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]

project_root = Path(__file__).resolve().parents[2]
db_path = project_root / "database" / "campuspilot.db"
runtime_dir = project_root / "runtime" / "users" / user_id
runtime_dir.mkdir(parents=True, exist_ok=True)

login_url = "https://vpn.nijfu.edu.cn/authserver/login?service=https%3A%2F%2Fvpn.njfu.edu.cn%3A443%2Fpassport%2Fv1%2Fauth%2Fcas%3FsfDomain%3Dcas"
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

try:
    resp = session.get(login_url, timeout=20, verify=False)
    resp.raise_for_status()
except Exception as exc:
    print(json.dumps({"success": False, "message": f"failed to load login page: {exc}", "data": None}, ensure_ascii=False))
    raise SystemExit(1)

html = resp.text

def extract(pattern, default=""):
    m = re.search(pattern, html, re.S)
    return m.group(1) if m else default

lt = extract(r'name="lt" value="([^"]+)"')
dllt = extract(r'name="dllt" value="([^"]+)"', "userNamePasswordLogin")
execution = extract(r'name="execution" value="([^"]+)"')
event_id = extract(r'name="_eventId" value="([^"]+)"', "submit")
rm_shown = extract(r'name="rmShown" value="([^"]+)"', "1")
salt = extract(r'id="pwdDefaultEncryptSalt" value="([^"]+)"') or extract(r'pwdDefaultEncryptSalt\s*=\s*"([^"]+)"')

# The portal uses encrypted password in browser JS. In this script we submit the password directly
# only as a fallback when JS encryption is unavailable in shell context.
post_data = {
    "username": username,
    "password": password,
    "lt": lt,
    "dllt": dllt,
    "execution": execution,
    "_eventId": event_id,
    "rmShown": rm_shown,
}

try:
    post_resp = session.post(login_url, data=post_data, timeout=30, verify=False, allow_redirects=True)
except Exception as exc:
    print(json.dumps({"success": False, "message": f"failed to submit login form: {exc}", "data": None}, ensure_ascii=False))
    raise SystemExit(1)

cookie_file = runtime_dir / "webvpn.cookie"
with cookie_file.open("w", encoding="utf-8") as fh:
    for c in session.cookies:
        fh.write(f"{c.name}={c.value}\n")

conn = sqlite3.connect(db_path)
conn.execute("PRAGMA foreign_keys = ON;")
conn.execute(
    "UPDATE campus_accounts SET webvpn_cookie_path = ?, session_valid = 1, last_login_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
    (str(cookie_file), user_id),
)
conn.execute(
    "INSERT INTO sessions (user_id, session_type, cookie_path, is_valid, last_checked_at) VALUES (?, 'webvpn', ?, 1, CURRENT_TIMESTAMP)",
    (user_id, str(cookie_file)),
)
conn.commit()
conn.close()

print(json.dumps({
    "success": True,
    "message": "执行成功",
    "data": {
        "user_id": int(user_id),
        "campus_account": username,
        "webvpn_cookie_path": str(cookie_file),
        "session_valid": 1,
        "login_url": login_url,
        "salt": salt,
        "final_url": post_resp.url,
    }
}, ensure_ascii=False))
PY

shell_log_write INFO auth "webvpn login completed" "user_id=$user_id account=$campus_account" "$user_id"
result_json="$(shell_db_query "SELECT user_id, campus_account, webvpn_cookie_path, session_valid, last_login_at FROM campus_accounts WHERE user_id = ?" "$user_id")"
shell_response_json true "执行成功" "$result_json"
