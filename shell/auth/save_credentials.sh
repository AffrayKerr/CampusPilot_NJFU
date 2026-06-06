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

user_id="${1:-}"
campus_account="${2:-}"
campus_password="${3:-}"

if [[ -z "$user_id" || -z "$campus_account" || -z "$campus_password" ]]; then
  shell_response_json false "user_id, campus_account and campus_password are required" null
  exit 1
fi

shell_db_init
shell_env_ensure_user_runtime_dir "$user_id" >/dev/null

encrypted_password="$(python - "$campus_password" <<'PY'
import base64
import sys
plain = sys.argv[1].encode('utf-8')
print(base64.urlsafe_b64encode(plain).decode('utf-8'))
PY
)"

shell_db_execute "INSERT INTO campus_accounts (user_id, campus_account, campus_password_encrypted, session_valid) VALUES (?, ?, ?, 0) ON CONFLICT(user_id) DO UPDATE SET campus_account = excluded.campus_account, campus_password_encrypted = excluded.campus_password_encrypted, updated_at = CURRENT_TIMESTAMP" "$user_id" "$campus_account" "$encrypted_password"
shell_log_write INFO auth "campus credentials saved" "user_id=$user_id account=$campus_account" "$user_id"

shell_response_json true "执行成功" "{}"
