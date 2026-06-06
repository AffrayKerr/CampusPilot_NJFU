#!/usr/bin/env python3
"""WebVPN login helper for CampusPilot shell auth scripts."""

from __future__ import annotations

import argparse
import base64
import json
import os
import random
import re
import sqlite3
import urllib3
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

WEBVPN_BASE = "https://webvpn.njfu.edu.cn"
CAS_HOST = "uia.njfu.edu.cn"
CAS_LOGIN_URL = f"https://{CAS_HOST}/authserver/login"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
RANDOM_CHARS = "ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678"


def emit(success: bool, message: str, data: Any = None, code: int | None = None) -> None:
    payload = {"success": success, "message": message, "data": data}
    print(json.dumps(payload, ensure_ascii=False))
    if code is not None:
        raise SystemExit(code)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def database_path() -> Path:
    env_path = os.environ.get("DATABASE_PATH")
    if env_path:
        return Path(env_path)
    return project_root() / "database" / "campuspilot.db"


def runtime_dir(user_id: str) -> Path:
    root = os.environ.get("USERS_RUNTIME_DIR")
    if root:
        path = Path(root) / user_id
    else:
        path = project_root() / "runtime" / "users" / user_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def cookie_path(user_id: str) -> Path:
    return runtime_dir(user_id) / "webvpn.cookie"


def new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
    )
    session.verify = False
    return session


def random_string(length: int) -> str:
    return "".join(random.choice(RANDOM_CHARS) for _ in range(length))


def encrypt_cas_password(password: str, salt: str) -> str:
    if not salt:
        return password
    payload = (random_string(64) + password).encode("utf-8")
    key = salt.strip().encode("utf-8")
    iv = random_string(16).encode("utf-8")
    padder = padding.PKCS7(128).padder()
    padded = padder.update(payload) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(ciphertext).decode("ascii")


def extract_field(html: str, pattern: str, default: str = "") -> str:
    match = re.search(pattern, html, re.S | re.I)
    return match.group(1) if match else default


def save_cookies(session: requests.Session, path: Path) -> None:
    lines: list[str] = []
    for cookie in session.cookies:
        domain = cookie.domain or ""
        if "njfu.edu.cn" not in domain:
            continue
        lines.append(f"{cookie.name}={cookie.value}|{domain}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def load_cookies(session: requests.Session, path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            parts = line.split("|")
            name_value = parts[0]
            domain = parts[1] if len(parts) > 1 and parts[1] else "webvpn.njfu.edu.cn"
            path_value = parts[2] if len(parts) > 2 and parts[2] else "/"
            if "=" in name_value:
                name, value = name_value.split("=", 1)
                session.cookies.set(name, value, domain=domain, path=path_value)
        elif "=" in line:
            name, value = line.split("=", 1)
            session.cookies.set(name, value, domain="webvpn.njfu.edu.cn")
            session.cookies.set(name, value, domain=".njfu.edu.cn")
            session.cookies.set(name, value, domain="uia.njfu.edu.cn")


def open_cas_login_page(session: requests.Session) -> tuple[str, str]:
    from urllib.parse import quote
    service = quote(WEBVPN_BASE + "/", safe="")
    url = f"{CAS_LOGIN_URL}?service={service}"
    response = session.get(url, timeout=30, allow_redirects=True)
    response.raise_for_status()
    final_url = response.url
    if CAS_HOST not in urlparse(final_url).netloc:
        raise RuntimeError(f"expected CAS login page, got: {final_url}")
    return final_url, response.text


def submit_cas_login(
    session: requests.Session, login_url: str, html: str, username: str, password: str
) -> requests.Response:
    salt = extract_field(
        html,
        r'id="pwdDefaultEncryptSalt"\s+value="([^"]+)"',
    ) or extract_field(html, r'pwdDefaultEncryptSalt\s*=\s*"([^"]+)"')
    if not salt:
        raise RuntimeError("CAS encrypt salt not found")

    if re.search(r'id="captchaImg"|isSliderCaptcha[^>]*value="true"', html, re.I):
        raise RuntimeError("CAS captcha required; automated login is not supported")

    form_action = extract_field(html, r'<form[^>]+id="casLoginForm"[^>]+action="([^"]+)"')
    post_url = urljoin(login_url, form_action or login_url)

    post_data = {
        "username": username,
        "password": encrypt_cas_password(password, salt),
        "lt": extract_field(html, r'name="lt"\s+value="([^"]+)"'),
        "dllt": extract_field(html, r'name="dllt"\s+value="([^"]+)"', "userNamePasswordLogin"),
        "execution": extract_field(html, r'name="execution"\s+value="([^"]+)"'),
        "_eventId": extract_field(html, r'name="_eventId"\s+value="([^"]+)"', "submit"),
        "rmShown": extract_field(html, r'name="rmShown"\s+value="([^"]+)"', "1"),
    }
    if not post_data["lt"] or not post_data["execution"]:
        raise RuntimeError("CAS login form tokens missing")

    session.headers["Referer"] = login_url
    session.headers["Content-Type"] = "application/x-www-form-urlencoded"
    response = session.post(post_url, data=post_data, timeout=40, allow_redirects=True)
    response.raise_for_status()
    session.headers.pop("Content-Type", None)
    return response


def session_is_online(session: requests.Session) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {}
    try:
        response = session.get(WEBVPN_BASE, timeout=20, allow_redirects=True)
        details["status_code"] = response.status_code
        details["final_url"] = response.url

        if CAS_HOST in urlparse(response.url).netloc:
            details["reason"] = "redirected to CAS login page"
            return False, details

        if "统一身份认证" in response.text and "casLoginForm" in response.text:
            details["reason"] = "CAS login form detected"
            return False, details

        # rump_frontend/login 是 webvpn 的 SSO 入口跳转页，到达此页说明 SSO 未完成
        if "rump_frontend/login" in response.url:
            details["reason"] = "webvpn login page, SSO not completed"
            return False, details

        # frontend_static/frontend/login/index.html#/ 是登录后的资源门户 SPA
        if WEBVPN_BASE in response.url and response.status_code == 200:
            details["reason"] = "webvpn accessible"
            return True, details

        details["reason"] = "unexpected state"
        return False, details
    except Exception as exc:
        details["error"] = str(exc)
        return False, details


def decode_bound_password(raw: str) -> str:
    try:
        return base64.urlsafe_b64decode(raw.encode("utf-8")).decode("utf-8")
    except Exception:
        return raw


def load_account(user_id: str, username: str | None = None, password: str | None = None) -> tuple[str, str]:
    if username and password:
        return username, password

    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT campus_account, campus_password_encrypted FROM campus_accounts WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    if row is None:
        raise RuntimeError("campus account is not bound")
    return row["campus_account"], decode_bound_password(row["campus_password_encrypted"])


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def persist_login_state(user_id: str, cookie_file: Path) -> dict[str, Any]:
    conn = db_connect()
    conn.execute(
        """
        UPDATE campus_accounts
        SET webvpn_cookie_path = ?, session_valid = 1,
            last_login_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
        """,
        (str(cookie_file), user_id),
    )
    conn.execute(
        """
        INSERT INTO sessions (user_id, session_type, cookie_path, is_valid, last_checked_at)
        VALUES (?, 'webvpn', ?, 1, CURRENT_TIMESTAMP)
        """,
        (user_id, str(cookie_file)),
    )
    conn.commit()
    row = conn.execute(
        """
        SELECT user_id, campus_account, webvpn_cookie_path, session_valid, last_login_at
        FROM campus_accounts WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


def mark_session_invalid(user_id: str) -> None:
    conn = db_connect()
    conn.execute(
        """
        UPDATE campus_accounts
        SET session_valid = 0, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
        """,
        (user_id,),
    )
    conn.execute(
        """
        UPDATE sessions
        SET is_valid = 0, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ? AND session_type = 'webvpn'
        """,
        (user_id,),
    )
    conn.commit()
    conn.close()


def cmd_login(user_id: str, username: str | None, password: str | None) -> None:
    account, plain_password = load_account(user_id, username, password)
    session = new_session()
    
    login_url, login_html = open_cas_login_page(session)
    
    if CAS_HOST not in urlparse(login_url).netloc:
        raise RuntimeError(f"expected CAS login page, got: {login_url}")
    
    post_resp = submit_cas_login(session, login_url, login_html, account, plain_password)
    
    online, details = session_is_online(session)
    if not online:
        if CAS_HOST in urlparse(post_resp.url).netloc:
            raise RuntimeError("CAS login rejected; still on authentication page")
        raise RuntimeError(f"webvpn login finished but session is offline: {details}")
    
    cookie_file = cookie_path(user_id)
    save_cookies(session, cookie_file)
    data = persist_login_state(user_id, cookie_file)
    data.update(
        {
            "final_url": post_resp.url,
            "online_details": details,
        }
    )
    emit(True, "执行成功", data, 0)


def cmd_check(user_id: str) -> None:
    path = cookie_path(user_id)
    if not path.is_file():
        mark_session_invalid(user_id)
        emit(False, "session cookie not found", None, 1)
    
    session = new_session()
    load_cookies(session, path)
    online, details = session_is_online(session)
    if not online:
        mark_session_invalid(user_id)
        emit(False, "session invalid", details, 1)
    
    conn = db_connect()
    conn.execute(
        """
        UPDATE campus_accounts
        SET session_valid = 1, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
        """,
        (user_id,),
    )
    conn.commit()
    row = conn.execute(
        """
        SELECT session_valid, webvpn_cookie_path, last_login_at
        FROM campus_accounts WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    conn.close()
    data = dict(row) if row else {}
    if details:
        data = {"session": data, "online_details": details}
    emit(True, "执行成功", data, 0)


def cmd_logout(user_id: str) -> None:
    path = cookie_path(user_id)
    if path.is_file():
        path.unlink(missing_ok=True)
    
    mark_session_invalid(user_id)
    conn = db_connect()
    conn.execute(
        """
        UPDATE campus_accounts
        SET webvpn_cookie_path = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
        """,
        (user_id,),
    )
    conn.commit()
    conn.close()
    emit(True, "执行成功", {}, 0)


def main() -> None:
    parser = argparse.ArgumentParser(description="CampusPilot WebVPN client")
    parser.add_argument("action", choices=["login", "check", "logout"])
    parser.add_argument("user_id")
    parser.add_argument("username", nargs="?", default=None)
    parser.add_argument("password", nargs="?", default=None)
    args = parser.parse_args()
    
    try:
        if args.action == "login":
            cmd_login(args.user_id, args.username, args.password)
        elif args.action == "check":
            cmd_check(args.user_id)
        else:
            cmd_logout(args.user_id)
    except Exception as exc:
        emit(False, str(exc), None, 1)


if __name__ == "__main__":
    main()
