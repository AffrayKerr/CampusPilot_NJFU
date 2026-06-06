import os
from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parents[1]
    PROJECT_ROOT = BASE_DIR
    DATABASE_PATH = BASE_DIR / "database" / "campuspilot.db"
    SHELL_TIMEOUT = 30
    JSON_AS_ASCII = False
    SECRET_KEY = os.getenv("CAMPUSPILOT_SECRET_KEY", "campuspilot-dev-secret-key")
    SESSION_COOKIE_NAME = "campuspilot_session"
    SESSION_TTL_HOURS = int(os.getenv("CAMPUSPILOT_SESSION_TTL_HOURS", "24"))
    ENCRYPTION_KEY = os.getenv("CAMPUSPILOT_ENCRYPTION_KEY", "")
    ADMIN_EMAIL = os.getenv("CAMPUSPILOT_ADMIN_EMAIL", "")
