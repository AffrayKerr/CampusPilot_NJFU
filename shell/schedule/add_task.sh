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
title="${2:-}"
deadline="${3:-}"
priority="${4:-medium}"
category="${5:-}"
repeat_rule="${6:-none}"
reminder_time="${7:-}"
note="${8:-}"

if [[ -z "$user_id" || -z "$title" || -z "$deadline" ]]; then
  shell_response_json false "user_id, title and deadline are required" null
  exit 1
fi

shell_db_init

shell_db_execute \
  "INSERT INTO tasks (user_id, title, deadline, priority, category, repeat_rule, reminder_time, note, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')" \
  "$user_id" "$title" "$deadline" "$priority" "$category" "$repeat_rule" "$reminder_time" "$note"

task_id="$(shell_db_query "SELECT last_insert_rowid() as id" | python -c "import json, sys; print(json.load(sys.stdin)[0]['id'])")"

shell_log_write INFO schedule "task added" "user_id=$user_id task_id=$task_id title=$title" "$user_id"

shell_response_json true "task added" "{\"task_id\": $task_id, \"title\": \"$title\"}"
