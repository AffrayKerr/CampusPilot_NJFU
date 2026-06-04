#!/usr/bin/env bash
set -eu

# shellcheck source=../common/env.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../common/env.sh"

shell_auth_python() {
  if [[ -x "$PROJECT_ROOT/.venv/Scripts/python.exe" ]]; then
    echo "$PROJECT_ROOT/.venv/Scripts/python.exe"
  elif [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
    echo "$PROJECT_ROOT/.venv/bin/python"
  else
    echo "python"
  fi
}
