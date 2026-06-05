#!/usr/bin/env bash
set -eu

# shellcheck source=../common/env.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../common/env.sh"

shell_auth_python() {
  if [[ -n "${SHELL_AUTH_PYTHON:-}" ]]; then
    echo "$SHELL_AUTH_PYTHON"
  elif command -v python3 >/dev/null 2>&1; then
    echo "python3"
  elif [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
    echo "$PROJECT_ROOT/.venv/bin/python"
  else
    echo "python"
  fi
}
