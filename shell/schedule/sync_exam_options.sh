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
# shellcheck source=../common/db.sh
source "$SCRIPT_DIR/../common/db.sh"

user_id="${1:-}"
if [[ -z "$user_id" ]]; then
  shell_response_json false "user_id is required" null
  exit 1
fi

shell_db_init
shell_env_ensure_user_runtime_dir "$user_id" >/dev/null

script_path="$SCRIPT_DIR/exam_scraper.py"
if [[ "$EXAM_PYTHON" == *.exe ]]; then
  if command -v cygpath >/dev/null 2>&1; then
    script_path="$(cygpath -w "$script_path")"
  elif command -v wslpath >/dev/null 2>&1; then
    script_path="$(wslpath -w "$script_path")"
  fi
fi

"$EXAM_PYTHON" "$script_path" exam_options "$user_id"
