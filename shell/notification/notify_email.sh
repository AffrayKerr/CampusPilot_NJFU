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
subject="${2:-}"
content="${3:-}"
to_addr="${4:-}"

if [[ -z "$user_id" || -z "$subject" || -z "$content" ]]; then
  shell_response_json false "user_id, subject, and content are required" null
  exit 1
fi

shell_db_init

if [[ -z "$to_addr" ]]; then
  to_json="$(shell_db_query "SELECT email FROM users WHERE username = ? OR CAST(id AS TEXT) = ?" "$user_id" "$user_id")"
  to_addr="$(echo "$to_json" | "$AUTH_PYTHON" -c "import json,sys; d=json.load(sys.stdin); print(d[0]['email'] if d and d[0]['email'] else '')")"
fi

if [[ -z "$to_addr" ]]; then
  shell_log_write WARNING notification "email skipped: no recipient address" "user_id=$user_id" "$user_id"
  shell_response_json false "No recipient email address configured" null
  exit 1
fi

SMTP_HOST="${SMTP_HOST:-smtp.qq.com}"
SMTP_PORT="${SMTP_PORT:-587}"
SMTP_USER="${SMTP_USER:-}"
SMTP_PASS="${SMTP_PASS:-}"

if [[ -z "$SMTP_USER" || -z "$SMTP_PASS" ]]; then
  shell_log_write WARNING notification "email skipped: SMTP not configured" "user_id=$user_id" "$user_id"
  shell_response_json false "SMTP not configured (set SMTP_USER and SMTP_PASS)" null
  exit 1
fi

send_result="$("$AUTH_PYTHON" - "$SMTP_HOST" "$SMTP_PORT" "$SMTP_USER" "$SMTP_PASS" "$to_addr" "$subject" "$content" <<'PY' || true
import smtplib
import sys
import json
from email.mime.text import MIMEText
from email.header import Header

smtp_host, smtp_port, smtp_user, smtp_pass, to_addr, subject, content = sys.argv[1:]

try:
    msg = MIMEText(content, "plain", "utf-8")
    msg["From"] = smtp_user
    msg["To"] = to_addr
    msg["Subject"] = Header(subject, "utf-8")

    with smtplib.SMTP(smtp_host, int(smtp_port), timeout=10) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [to_addr], msg.as_string())

    print(json.dumps({"ok": True}))
except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}))
    sys.exit(1)
PY
)"

if [[ -z "$send_result" || "$send_result" == *'"ok": false'* || "$send_result" == *'"ok":false'* ]]; then
  err="$(echo "${send_result:-}" | "$AUTH_PYTHON" -c "import json,sys; d=json.loads(sys.stdin.read()); print(d.get('error','unknown'))" 2>/dev/null || echo "unknown")"
  shell_log_write ERROR notification "email send failed" "user_id=$user_id to=$to_addr error=$err" "$user_id"
  shell_response_json false "Email send failed: $err" null
  exit 1
fi

shell_log_write INFO notification "email sent" "user_id=$user_id to=$to_addr subject=$subject" "$user_id"
shell_response_json true "Email sent" "{\"to\": \"$to_addr\", \"subject\": \"$subject\"}"
