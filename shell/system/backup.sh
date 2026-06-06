#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../common/env.sh"
source "$SCRIPT_DIR/../common/response.sh"
source "$SCRIPT_DIR/../common/log.sh"

backup_dir="${1:-$PROJECT_ROOT/backups}"
timestamp=$(date +"%Y%m%d_%H%M%S")
backup_name="campuspilot_backup_$timestamp"
backup_path="$backup_dir/$backup_name"

mkdir -p "$backup_path"

if [[ -f "$DATABASE_PATH" ]]; then
  cp "$DATABASE_PATH" "$backup_path/campuspilot.db"
fi

if [[ -d "$USERS_RUNTIME_DIR" ]]; then
  cp -r "$USERS_RUNTIME_DIR" "$backup_path/users_runtime" 2>/dev/null || true
fi

if [[ -d "$LOG_DIR" ]]; then
  cp -r "$LOG_DIR" "$backup_path/logs" 2>/dev/null || true
fi

cd "$backup_dir" || exit 1
tar -czf "$backup_name.tar.gz" "$backup_name" 2>/dev/null
backup_file="$backup_dir/$backup_name.tar.gz"
rm -rf "$backup_path"

if [[ -f "$backup_file" ]]; then
  backup_size=$(stat -c%s "$backup_file" 2>/dev/null || stat -f%z "$backup_file" 2>/dev/null || echo "0")
  shell_log_write INFO system "数据备份完成" "backup=$backup_file size=$backup_size"
  shell_response_json true "数据备份完成" "{\"backup_file\": \"$backup_file\", \"size_bytes\": $backup_size}"
else
  shell_response_json false "数据备份失败" null
  exit 1
fi
