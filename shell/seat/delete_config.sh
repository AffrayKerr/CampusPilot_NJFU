#!/usr/bin/env bash
set -eu

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../common/env.sh
source "$script_dir/../common/env.sh"
# shellcheck source=../common/db.sh
source "$script_dir/../common/db.sh"
# shellcheck source=../common/response.sh
source "$script_dir/../common/response.sh"
# shellcheck source=../common/log.sh
source "$script_dir/../common/log.sh"

user_id="${1:-}"
config_id="${2:-}"

if [[ -z "$user_id" || -z "$config_id" ]]; then
  shell_response_json false "Missing required parameters: user_id, config_id"
  exit 1
fi

shell_db_execute "DELETE FROM seat_configs WHERE id = ? AND user_id = ?" "$config_id" "$user_id"

shell_log_write "INFO" "seat" "Seat config deleted" "config_id=$config_id" "$user_id"

shell_response_json true "Seat config deleted" "{}"
