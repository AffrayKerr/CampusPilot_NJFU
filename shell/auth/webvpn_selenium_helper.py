#!/usr/bin/env python3
"""Interactive WebVPN login helper using Selenium.

This script opens a browser window and waits for the user to manually
complete the WebVPN login process, then automatically extracts cookies.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.common.exceptions import TimeoutException, WebDriverException
except ImportError:
    print(json.dumps({
        "success": False,
        "message": "selenium is not installed. Run: pip install selenium",
        "data": None
    }, ensure_ascii=False))
    sys.exit(1)

WEBVPN_BASE = "https://webvpn.njfu.edu.cn"
JWC_MAIN_URL = (
    "https://webvpn.njfu.edu.cn/webvpn/LjIwMS4xNjkuMjE4LjE2OC4xNjc=/"
    "LjIwMy4xNzIuMjIyLjE3Mi45OC4xNjMuMjA2LjE1My4yMTguOTYuMTU3LjE1Ni4yMTkuMTAwLjE1NC4yMTA="
    "/jsxsd/framework/xsMainV.jsp?vpn-0"
)
TIMEOUT_SECONDS = 600


def emit(success: bool, message: str, data: Any = None, code: int = 0) -> None:
    payload = {"success": success, "message": message, "data": data}
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(code)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def user_runtime_dir(user_id: str) -> Path:
    runtime_dir = project_root() / "runtime" / "users" / user_id
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def cookie_path(user_id: str) -> Path:
    return user_runtime_dir(user_id) / "webvpn.cookie"


def chrome_profile_path(user_id: str) -> Path:
    path = user_runtime_dir(user_id) / "chrome_profile"
    path.mkdir(parents=True, exist_ok=True)
    return path


def setup_driver(user_id: str) -> webdriver.Chrome:
    options = Options()
    options.add_argument(f"--user-data-dir={chrome_profile_path(user_id)}")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    try:
        driver = webdriver.Chrome(options=options)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
        return driver
    except WebDriverException as e:
        if "chromedriver" in str(e).lower() or "chrome" in str(e).lower():
            emit(False, "Chrome or ChromeDriver not found. Please install Chrome browser.", None, 1)
        else:
            emit(False, f"Failed to start browser: {str(e)}", None, 1)


def wait_for_webvpn_login(driver: webdriver.Chrome, timeout: int) -> bool:
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: "frontend_static/frontend/login/index.html" in d.current_url
        )
        return True
    except TimeoutException:
        return False


def warmup_jwc_session(driver: webdriver.Chrome) -> None:
    """Navigate to JWC through WebVPN so browser completes SSO and establishes JWC session cookies."""
    driver.get(JWC_MAIN_URL)
    try:
        WebDriverWait(driver, 60).until(
            lambda d: (
                ("jsxsd" in d.current_url or "htmlx" in d.current_url)
                and "uia.njfu.edu.cn" not in d.current_url
                and "authserver/login" not in d.current_url
            )
        )
    except TimeoutException:
        pass
    time.sleep(2)


def extract_cookies(driver: webdriver.Chrome) -> list[dict[str, str]]:
    # Use CDP to get ALL cookies across all domains/paths (more complete than driver.get_cookies())
    try:
        result = driver.execute_cdp_cmd("Network.getAllCookies", {})
        all_cookies = result.get("cookies", [])
    except Exception:
        all_cookies = driver.get_cookies()

    njfu_cookies = []
    seen = set()
    for c in all_cookies:
        domain = c.get("domain", "")
        name = c.get("name", "")
        if "njfu.edu.cn" not in domain:
            continue
        key = (name, domain, c.get("path", "/"))
        if key in seen:
            continue
        seen.add(key)
        njfu_cookies.append({
            "name": name,
            "value": c.get("value", ""),
            "domain": domain,
            "path": c.get("path", "/"),
        })

    print(json.dumps({
        "status": "cookies_extracted",
        "count": len(njfu_cookies),
        "names": [c["name"] for c in njfu_cookies],
    }, ensure_ascii=False), file=sys.stderr)

    return njfu_cookies


def save_cookies(cookies: list[dict[str, str]], path: Path) -> None:
    lines = []
    for c in cookies:
        domain = c.get("domain", "")
        cookie_path = c.get("path", "/")
        lines.append(f"{c['name']}={c['value']}|{domain}|{cookie_path}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_database(user_id: str, cookie_file: Path) -> None:
    import os
    import sqlite3 as _sqlite3
    env_path = os.environ.get("DATABASE_PATH")
    if env_path:
        db_path = env_path
    else:
        db_path = str(Path(__file__).resolve().parents[2] / "database" / "campus_pilot.db")

    conn = _sqlite3.connect(db_path)
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
    conn.close()


def main() -> None:
    if len(sys.argv) < 2:
        emit(False, "user_id is required", None, 1)

    user_id = sys.argv[1]
    cookie_file = cookie_path(user_id)

    driver = setup_driver(user_id)

    try:
        driver.get(WEBVPN_BASE)

        print(json.dumps({
            "status": "waiting",
            "message": f"Please complete login in the browser window (timeout: {TIMEOUT_SECONDS}s)",
            "current_url": driver.current_url
        }, ensure_ascii=False), file=sys.stderr)

        if not wait_for_webvpn_login(driver, TIMEOUT_SECONDS):
            emit(False, f"login timeout after {TIMEOUT_SECONDS} seconds", None, 1)

        time.sleep(1)

        # After WebVPN login, visit JWC so browser completes SSO and gets JWC session cookies
        warmup_jwc_session(driver)

        cookies = extract_cookies(driver)

        if not cookies:
            emit(False, "no cookies found after login", None, 1)

        save_cookies(cookies, cookie_file)
        update_database(user_id, cookie_file)

        emit(True, "interactive login completed", {
            "cookie_count": len(cookies),
            "cookie_file": str(cookie_file),
            "chrome_profile": str(chrome_profile_path(user_id)),
            "final_url": driver.current_url,
        }, 0)

    except Exception as e:
        emit(False, f"unexpected error: {str(e)}", None, 1)

    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
