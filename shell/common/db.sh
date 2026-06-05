#!/usr/bin/env bash
set -eu

# shellcheck source=./env.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/env.sh"

shell_db_init() {
  python3 - "$DATABASE_PATH" <<'PY'
import sqlite3
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(path)
conn.execute("PRAGMA foreign_keys = ON;")
conn.close()
PY
}

shell_db_query() {
  local sql="$1"
  shift || true
  python3 - "$DATABASE_PATH" "$sql" "$@" <<'PY'
import json
import sqlite3
import sys

path = sys.argv[1]
sql = sys.argv[2]
params = sys.argv[3:]
conn = sqlite3.connect(path)
conn.row_factory = sqlite3.Row
cur = conn.execute(sql, params)
rows = [dict(row) for row in cur.fetchall()]
conn.close()
print(json.dumps(rows, ensure_ascii=False))
PY
}

shell_db_execute() {
  local sql="$1"
  shift || true
  python3 - "$DATABASE_PATH" "$sql" "$@" <<'PY'
import sqlite3
import sys

path = sys.argv[1]
sql = sys.argv[2]
params = sys.argv[3:]
conn = sqlite3.connect(path)
conn.execute("PRAGMA foreign_keys = ON;")
conn.execute(sql, params)
conn.commit()
conn.close()
PY
}
