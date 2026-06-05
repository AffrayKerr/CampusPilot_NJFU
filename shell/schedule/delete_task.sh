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
task_id="${2:-}"

if [[ -z "$user_id" || -z "$task_id" ]]; then
  shell_response_json false "user_id and task_id are required" null
  exit 1
fi

shell_db_init

row_json="$(shell_db_query "SELECT id FROM tasks WHERE id = ? AND user_id = ?" "$task_id" "$user_id")"
if [[ "$row_json" == "[]" ]]; then
  shell_response_json false "task not found or access denied" null
  exit 1
fi

shell_db_execute "DELETE FROM tasks WHERE id = ? AND user_id = ?" "$task_id" "$user_id"

shell_log_write INFO schedule "task deleted" "user_id=$user_id task_id=$task_id" "$user_id"

shell_response_json true "task deleted" "{\"task_id\": $task_id}"
