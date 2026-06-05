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

user_id="${1:-}"
title="${2:-}"
content="${3:-}"

if [[ -z "$user_id" || -z "$title" || -z "$content" ]]; then
  shell_response_json false "user_id, title, and content are required" null
  exit 1
fi

MAX_LENGTH=100
if [[ ${#content} -gt $MAX_LENGTH ]]; then
  content="${content:0:$MAX_LENGTH}..."
fi

if command -v notify-send >/dev/null 2>&1; then
  if notify-send "$title" "$content" 2>/dev/null; then
    shell_log_write INFO notification "desktop notification sent" "title=$title user_id=$user_id" "$user_id"
    shell_response_json true "Desktop notification sent" "{\"title\": \"$title\"}"
    exit 0
  else
    shell_log_write WARNING notification "notify-send failed" "user_id=$user_id" "$user_id"
    shell_response_json false "Failed to send desktop notification" null
    exit 1
  fi
else
  shell_log_write WARNING notification "notify-send not available" "user_id=$user_id" "$user_id"
  shell_response_json false "Desktop notification not supported on this system" null
  exit 1
fi
