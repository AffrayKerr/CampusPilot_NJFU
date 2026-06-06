#!/usr/bin/env bash
set -eu

shell_response_json() {
  local success="${1:-true}"
  local message="${2:-执行成功}"
  local data="${3}"
  if [[ -z "${data+x}" || "$#" -lt 3 ]]; then
    data='{}'
  fi

  python - "$success" "$message" "$data" <<'PY'
import json
import sys

success = sys.argv[1].lower() == 'true'
message = sys.argv[2]
raw_data = sys.argv[3]

try:
    data = json.loads(raw_data)
except Exception:
    data = raw_data

print(json.dumps({"success": success, "message": message, "data": data}, ensure_ascii=False))
PY
}
