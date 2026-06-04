#!/usr/bin/env bash
set -eu

# shellcheck source=./env.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/env.sh"

shell_cookie_path() {
  local user_id="${1:-}"
  local user_dir
  user_dir="$(shell_env_ensure_user_runtime_dir "$user_id")"
  echo "$user_dir/webvpn.cookie"
}

shell_cookie_save() {
  local user_id="${1:-}"
  local cookie_content="${2:-}"
  local cookie_file
  cookie_file="$(shell_cookie_path "$user_id")"
  printf '%s' "$cookie_content" > "$cookie_file"
  echo "$cookie_file"
}

shell_cookie_read() {
  local user_id="${1:-}"
  local cookie_file
  cookie_file="$(shell_cookie_path "$user_id")"
  if [[ -f "$cookie_file" ]]; then
    cat "$cookie_file"
  fi
}

shell_cookie_delete() {
  local user_id="${1:-}"
  local cookie_file
  cookie_file="$(shell_cookie_path "$user_id")"
  rm -f "$cookie_file"
}
