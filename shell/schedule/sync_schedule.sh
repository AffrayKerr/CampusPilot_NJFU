#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../auth/runtime.sh
source "$SCRIPT_DIR/../auth/runtime.sh"
AUTH_PYTHON="$(shell_auth_python)"
SCHEDULE_PYTHON="$(shell_selenium_python)"
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

if ! auth_check_json="$("$AUTH_PYTHON" "$SCRIPT_DIR/../auth/webvpn_client.py" check "$user_id" 2>&1)"; then
  shell_log_write WARNING schedule "webvpn session invalid before schedule sync" "user_id=$user_id result=$auth_check_json" "$user_id"
  shell_response_json false "webvpn session invalid; please run auth login first" null
  exit 1
fi

shell_log_write INFO schedule "syncing schedule" "user_id=$user_id" "$user_id"

script_path="$SCRIPT_DIR/schedule_scraper.py"
if [[ "$SCHEDULE_PYTHON" == *.exe ]]; then
  script_path="$(wslpath -w "$script_path")"
fi

sync_timeout="${SCHEDULE_SYNC_TIMEOUT:-90}"
set +e
if command -v timeout >/dev/null 2>&1 && [[ "$SCHEDULE_PYTHON" != *.exe ]]; then
  result_json="$(timeout "$sync_timeout" "$SCHEDULE_PYTHON" "$script_path" sync_schedule "$user_id")"
  exit_code="$?"
else
  result_json="$("$SCHEDULE_PYTHON" "$script_path" sync_schedule "$user_id")"
  exit_code="$?"
fi
set -e

if [[ "$exit_code" != "0" ]]; then
  shell_log_write ERROR schedule "sync schedule failed" "user_id=$user_id exit_code=$exit_code result=$result_json" "$user_id"
  if [[ "$exit_code" == "124" ]]; then
    shell_response_json false "sync schedule timeout after ${sync_timeout}s" null
  elif [[ -n "${result_json:-}" && "$result_json" == *'"success"'* ]]; then
    printf '%s\n' "$result_json"
  else
    shell_response_json false "sync schedule failed" null
  fi
  exit 1
fi

shell_log_write INFO schedule "schedule synced" "user_id=$user_id" "$user_id"
printf '%s\n' "$result_json"
