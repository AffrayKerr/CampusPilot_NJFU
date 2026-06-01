from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parents[1]
    PROJECT_ROOT = BASE_DIR
    DATABASE_PATH = BASE_DIR / "database" / "campuspilot.db"
    SHELL_TIMEOUT = 30
    JSON_AS_ASCII = False
