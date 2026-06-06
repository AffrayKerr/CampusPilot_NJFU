#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../common/env.sh"
source "$SCRIPT_DIR/../common/response.sh"
source "$SCRIPT_DIR/../common/db.sh"

user_id="${1:-}"
module="${2:-}"
level="${3:-}"
limit="${4:-50}"

if [[ -z "$user_id" ]]; then
  shell_response_json false "user_id is required" null
  exit 1
fi

shell_db_init

result_json=$(shell_common_python - "$DATABASE_PATH" "$user_id" "$module" "$level" "$limit" <<'PY'
import json
import sqlite3
import sys

db_path = sys.argv[1]
user_id = sys.argv[2]
module = sys.argv[3]
level = sys.argv[4]
limit = int(sys.argv[5])

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

where_clauses = ["user_id = ?"]
params = [user_id]

if module:
    where_clauses.append("module = ?")
    params.append(module)

if level:
    where_clauses.append("level = ?")
    params.append(level)

where_sql = " AND ".join(where_clauses)
sql = f"""
SELECT id, user_id, module, level, message, detail,
       strftime('%Y-%m-%d %H:%M:%S', created_at, 'localtime') AS created_at
FROM logs
WHERE {where_sql}
ORDER BY created_at DESC
LIMIT ?
"""
params.append(limit)

cur = conn.execute(sql, params)
logs = [dict(row) for row in cur.fetchall()]
conn.close()

print(json.dumps({"success": True, "message": "查询成功", "data": {"logs": logs}}, ensure_ascii=False))
PY
)

printf '%s\n' "$result_json"
