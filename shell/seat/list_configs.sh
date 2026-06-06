#!/usr/bin/env bash
set -eu

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../common/env.sh
source "$script_dir/../common/env.sh"
# shellcheck source=../common/db.sh
source "$script_dir/../common/db.sh"
# shellcheck source=../common/response.sh
source "$script_dir/../common/response.sh"

user_id="${1:-}"

if [[ -z "$user_id" ]]; then
  shell_response_json false "Missing required parameter: user_id"
  exit 1
fi

configs=$(shell_db_query "SELECT * FROM seat_configs WHERE user_id = ? ORDER BY priority ASC, id ASC" "$user_id")

shell_response_json true "Seat configs retrieved" "$configs"
