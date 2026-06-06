import sqlite3
from pathlib import Path

from flask import current_app, has_app_context

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "database" / "campuspilot.db"
SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.sql"


def get_database_path():
    if has_app_context():
        return Path(current_app.config.get("DATABASE_PATH", DEFAULT_DATABASE_PATH))
    return DEFAULT_DATABASE_PATH


def get_connection():
    database_path = get_database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_database():
    with get_connection() as conn:
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema_sql)
        conn.commit()


def fetch_one(query, params=None):
    params = params or []
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None


def fetch_all(query, params=None):
    params = params or []
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def execute(query, params=None):
    params = params or []
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        conn.commit()
        return cursor.lastrowid
