#!/usr/bin/env bash
set -eu

script_dir=$(dirname "$0")
script_dir=$(cd "$script_dir" && pwd)
# shellcheck source=../auth/runtime.sh
source "$script_dir/../auth/runtime.sh"
SEAT_PYTHON=$(shell_auth_python)
# shellcheck source=../common/env.sh
source "$script_dir/../common/env.sh"
# shellcheck source=../common/response.sh
source "$script_dir/../common/response.sh"
# shellcheck source=../common/log.sh
source "$script_dir/../common/log.sh"

user_id="${1:-}"

if [[ -z "$user_id" ]]; then
  shell_response_json false "Missing required parameter: user_id"
  exit 1
fi

"$SEAT_PYTHON" "$script_dir/seat_client.py" retry "$user_id"
