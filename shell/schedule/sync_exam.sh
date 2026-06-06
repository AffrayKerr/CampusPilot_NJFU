#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../auth/runtime.sh
source "$SCRIPT_DIR/../auth/runtime.sh"
EXAM_PYTHON="$(shell_selenium_python)"
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

script_path="$SCRIPT_DIR/exam_scraper.py"
if [[ "$EXAM_PYTHON" == *.exe ]]; then
  if command -v cygpath >/dev/null 2>&1; then
    script_path="$(cygpath -w "$script_path")"
  elif command -v wslpath >/dev/null 2>&1; then
    script_path="$(wslpath -w "$script_path")"
  fi
fi

exam_timeout="${EXAM_SYNC_TIMEOUT:-140}"
stderr_file="$(mktemp)"
set +e
if command -v timeout >/dev/null 2>&1 && [[ "$EXAM_PYTHON" != *.exe ]]; then
  result_json="$(timeout "$exam_timeout" "$EXAM_PYTHON" "$script_path" sync_exam "$user_id" 2>"$stderr_file")"
  exit_code="$?"
else
  result_json="$("$EXAM_PYTHON" "$script_path" sync_exam "$user_id" 2>"$stderr_file")"
  exit_code="$?"
fi
stderr_text="$(cat "$stderr_file" 2>/dev/null || true)"
rm -f "$stderr_file"
set -e

if [[ "$exit_code" != "0" ]]; then
  shell_log_write ERROR schedule "sync exam failed" "user_id=$user_id exit_code=$exit_code result=$result_json stderr=$stderr_text" "$user_id"
  if [[ "$exit_code" == "124" ]]; then
    result_json="$(shell_response_json false "考试安排同步超时，请确认教务网登录状态后重试" null)"
  elif [[ -z "$result_json" || "$result_json" != *'"success"'* ]]; then
    result_json="$(shell_response_json false "sync exam failed" null)"
  fi
  printf '%s\n' "$result_json"
  exit 1
fi

shell_log_write INFO schedule "exams synced" "user_id=$user_id result=$result_json stderr=$stderr_text" "$user_id"
printf '%s\n' "$result_json"
