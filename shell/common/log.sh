#!/usr/bin/env bash
set -eu

# shellcheck source=./env.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/env.sh"

shell_log_write() {
  local level="${1:-INFO}"
  local module="${2:-system}"
  local message="${3:-}"
  local detail="${4:-}"
  local user_id="${5:-}"

  local log_file="$LOG_DIR/system.log"
  if [[ -n "$user_id" ]]; then
    local user_dir
    user_dir="$(shell_env_ensure_user_runtime_dir "$user_id")"
    log_file="$user_dir/runtime.log"
  else
    mkdir -p "$LOG_DIR"
  fi

  python - "$log_file" "$level" "$module" "$message" "$detail" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

log_file = Path(sys.argv[1])
entry = {
    "timestamp": datetime.now().isoformat(),
    "level": sys.argv[2],
    "module": sys.argv[3],
    "message": sys.argv[4],
    "detail": sys.argv[5],
}
log_file.parent.mkdir(parents=True, exist_ok=True)
with log_file.open('a', encoding='utf-8') as fh:
    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
PY
}
