#!/usr/bin/env bash
set -eu

# shellcheck source=../common/env.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../common/env.sh"

shell_auth_python() {
  if [[ -n "${SHELL_AUTH_PYTHON:-}" ]]; then
    echo "$SHELL_AUTH_PYTHON"
  elif [[ -x "$PROJECT_ROOT/.venv/Scripts/python.exe" ]]; then
    echo "$PROJECT_ROOT/.venv/Scripts/python.exe"
  elif [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
    echo "$PROJECT_ROOT/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    echo "python3"
  else
    echo "python"
  fi
}

shell_selenium_python() {
  if [[ -n "${SHELL_SELENIUM_PYTHON:-}" ]]; then
    echo "$SHELL_SELENIUM_PYTHON"
  elif [[ -x "$PROJECT_ROOT/.venv/Scripts/python.exe" ]]; then
    echo "$PROJECT_ROOT/.venv/Scripts/python.exe"
  elif [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
    echo "$PROJECT_ROOT/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    echo "python3"
  else
    echo "python"
  fi
}
