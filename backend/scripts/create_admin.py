import argparse
import getpass
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app
from services.auth_service import hash_password
from services.db import execute, fetch_one, init_database
from utils.validators import validate_password, validate_username


def parse_args():
    parser = argparse.ArgumentParser(description="Create a CampusPilot admin account")
    parser.add_argument("--username", help="Admin username")
    parser.add_argument("--password", help="Admin password")
    parser.add_argument("--email", default="", help="Admin email")
    return parser.parse_args()


def read_credentials(args):
    username = args.username or input("Admin username: ").strip()
    password = args.password or getpass.getpass("Admin password: ")
    email = args.email or input("Admin email(optional): ").strip()
    return username, password, email


def create_admin(username, password, email):
    init_database()

    if not validate_username(username):
        raise ValueError("Invalid username")

    if not validate_password(password):
        raise ValueError("Password must be at least 6 characters")

    existing_user = fetch_one("SELECT id FROM users WHERE username = ?", [username])
    if existing_user:
        raise ValueError("Username already exists")

    user_id = execute(
        """
        INSERT INTO users (username, password_hash, role, email)
        VALUES (?, ?, 'admin', ?)
        """,
        [username, hash_password(password), email],
    )
    execute(
        "INSERT INTO notification_settings (user_id, enable_email, enable_desktop) VALUES (?, ?, ?)",
        [user_id, 1 if email else 0, 1],
    )
    return user_id


def main():
    args = parse_args()
    username, password, email = read_credentials(args)
    app = create_app()

    with app.app_context():
        try:
            user_id = create_admin(username, password, email)
        except ValueError as exc:
            print(f"Failed to create admin: {exc}")
            return 1

    print(f"Admin account created successfully: {username} (id={user_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
