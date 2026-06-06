#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../common/env.sh"
source "$SCRIPT_DIR/../common/response.sh"
source "$SCRIPT_DIR/../common/log.sh"

SCHEMA_FILE="$PROJECT_ROOT/database/schema.sql"
MIGRATIONS_DIR="$PROJECT_ROOT/database/migrations"

if [[ ! -f "$SCHEMA_FILE" ]]; then
  shell_response_json false "schema.sql not found: $SCHEMA_FILE" null
  exit 1
fi

python3 - "$DATABASE_PATH" "$SCHEMA_FILE" "$MIGRATIONS_DIR" <<'PY'
import sqlite3
import sys
from pathlib import Path

db_path = Path(sys.argv[1])
schema_file = Path(sys.argv[2])
migrations_dir = Path(sys.argv[3])

db_path.parent.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(db_path)
conn.execute("PRAGMA foreign_keys = ON;")

conn.executescript(schema_file.read_text(encoding="utf-8"))
conn.commit()

if migrations_dir.is_dir():
    for migration in sorted(migrations_dir.glob("*.sql")):
        try:
            conn.executescript(migration.read_text(encoding="utf-8"))
            conn.commit()
        except Exception as e:
            pass

conn.close()
print("ok")
PY

if [[ $? -eq 0 ]]; then
  shell_log_write INFO system "数据库初始化完成" "db=$DATABASE_PATH"
  shell_response_json true "数据库初始化完成" "{\"db_path\": \"$DATABASE_PATH\"}"
else
  shell_response_json false "数据库初始化失败" null
  exit 1
fi
