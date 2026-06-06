#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../auth/runtime.sh
source "$SCRIPT_DIR/../auth/runtime.sh"
AUTH_PYTHON="$(shell_auth_python)"
# shellcheck source=../common/env.sh
source "$SCRIPT_DIR/../common/env.sh"
# shellcheck source=../common/response.sh
source "$SCRIPT_DIR/../common/response.sh"
# shellcheck source=../common/log.sh
source "$SCRIPT_DIR/../common/log.sh"

user_id="${1:-}"
channel="${2:-all}"
title="${3:-CampusPilot 测试通知}"
content="${4:-通知功能测试成功}"

if [[ -z "$user_id" ]]; then
  shell_response_json false "user_id is required" null
  exit 1
fi

if [[ "$channel" != "email" && "$channel" != "desktop" && "$channel" != "all" ]]; then
  shell_response_json false "channel must be email, desktop, or all" null
  exit 1
fi

results='{"email": null, "desktop": null}'

if [[ "$channel" == "email" || "$channel" == "all" ]]; then
  email_result="$(bash "$SCRIPT_DIR/notify_email.sh" "$user_id" "$title" "$content" "" 2>&1 || true)"
  if [[ "$email_result" == *'"success": true'* || "$email_result" == *'"success":true'* ]]; then
    results="$(echo "$results" | "$AUTH_PYTHON" -c "import json,sys; d=json.loads(sys.stdin.read()); d['email']='success'; print(json.dumps(d))")"
  else
    email_msg="$(echo "$email_result" | "$AUTH_PYTHON" -c "import json,sys; d=json.loads(sys.stdin.read()); print(d.get('message','failed'))" 2>/dev/null || echo "failed")"
    results="$(echo "$results" | "$AUTH_PYTHON" -c "import json,sys; d=json.loads(sys.stdin.read()); d['email']='$email_msg'; print(json.dumps(d))")"
  fi
fi

if [[ "$channel" == "desktop" || "$channel" == "all" ]]; then
  desktop_result="$(bash "$SCRIPT_DIR/notify_desktop.sh" "$user_id" "$title" "$content" 2>&1 || true)"
  if [[ "$desktop_result" == *'"success": true'* || "$desktop_result" == *'"success":true'* ]]; then
    results="$(echo "$results" | "$AUTH_PYTHON" -c "import json,sys; d=json.loads(sys.stdin.read()); d['desktop']='success'; print(json.dumps(d))")"
  else
    desktop_msg="$(echo "$desktop_result" | "$AUTH_PYTHON" -c "import json,sys; d=json.loads(sys.stdin.read()); print(d.get('message','failed'))" 2>/dev/null || echo "failed")"
    results="$(echo "$results" | "$AUTH_PYTHON" -c "import json,sys; d=json.loads(sys.stdin.read()); d['desktop']='$desktop_msg'; print(json.dumps(d))")"
  fi
fi

shell_log_write INFO notification "test notification completed" "user_id=$user_id channel=$channel" "$user_id"
shell_response_json true "Test notification completed" "$results"
