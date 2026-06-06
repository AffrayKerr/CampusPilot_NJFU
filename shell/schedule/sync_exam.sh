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
if [[ -z "$user_id" ]]; then
  shell_response_json false "user_id is required" null
  exit 1
fi

shell_db_init
shell_env_ensure_user_runtime_dir "$user_id" >/dev/null

shell_log_write INFO schedule "syncing exams" "user_id=$user_id" "$user_id"

if ! result_json="$("$AUTH_PYTHON" "$SCRIPT_DIR/schedule_scraper.py" sync_exam "$user_id" 2>&1)"; then
  shell_log_write ERROR schedule "sync exam failed" "user_id=$user_id result=$result_json" "$user_id"
  if [[ -z "$result_json" || "$result_json" != *'"success"'* ]]; then
    result_json="$(shell_response_json false "sync exam failed" null)"
  fi
  printf '%s\n' "$result_json"
  exit 1
fi

shell_log_write INFO schedule "exams synced" "user_id=$user_id" "$user_id"
printf '%s\n' "$result_json"
