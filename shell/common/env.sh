#!/usr/bin/env bash
set -eu

shell_env_project_root() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cd "$script_dir/../.." >/dev/null 2>&1 && pwd
}

PROJECT_ROOT="${PROJECT_ROOT:-$(shell_env_project_root)}"
DATABASE_PATH="${DATABASE_PATH:-$PROJECT_ROOT/database/campus_pilot.db}"
RUNTIME_DIR="${RUNTIME_DIR:-$PROJECT_ROOT/runtime}"
USERS_RUNTIME_DIR="${USERS_RUNTIME_DIR:-$RUNTIME_DIR/users}"
LOG_DIR="${LOG_DIR:-$PROJECT_ROOT/logs}"

shell_env_user_runtime_dir() {
  local user_id="${1:-}"
  if [[ -z "$user_id" ]]; then
    echo ""
    return 1
  fi
  echo "$USERS_RUNTIME_DIR/$user_id"
}

shell_env_ensure_user_runtime_dir() {
  local user_id="${1:-}"
  local user_dir
  user_dir="$(shell_env_user_runtime_dir "$user_id")"
  mkdir -p "$user_dir" "$LOG_DIR"
  echo "$user_dir"
}
