#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from cryptography.fernet import Fernet
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:
    print(json.dumps({"success": False, "message": "selenium/cryptography is not installed", "data": None}, ensure_ascii=False))
    sys.exit(1)

WEBVPN_BASE = "https://webvpn.njfu.edu.cn"
LIBRARY_SSO_URL = "https://webvpn.njfu.edu.cn/rump_frontend/connect/?target=Library&id=12"
JWC_MAIN_URL = (
    "https://webvpn.njfu.edu.cn/webvpn/LjIwMS4xNjkuMjE4LjE2OC4xNjc=/"
    "LjIwMy4xNzIuMjIyLjE3Mi45OC4xNjMuMjA2LjE1My4yMTguOTYuMTU3LjE1Ni4yMTkuMTAwLjE1NC4yMTA="
    "/jsxsd/framework/xsMainV.jsp?vpn-0"
)
TIMEOUT_SECONDS = 600


def emit(success: bool, message: str, data: Any = None, code: int = 0) -> None:
    print(json.dumps({"success": success, "message": message, "data": data}, ensure_ascii=False))
    sys.exit(code)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def database_path() -> Path:
    return Path(os.environ.get("DATABASE_PATH", project_root() / "database" / "campuspilot.db"))


def user_runtime_dir(user_id: str) -> Path:
    path = project_root() / "runtime" / "users" / user_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def cookie_path(user_id: str) -> Path:
    return user_runtime_dir(user_id) / "webvpn.cookie"


def chrome_profile_path(user_id: str) -> Path:
    path = user_runtime_dir(user_id) / "chrome_profile"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_status_file(path: Path | None, payload: dict[str, Any]) -> None:
    if path:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def derive_key(raw_key: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode("utf-8")).digest())


def decrypt_password(cipher_text: str) -> str:
    raw_key = os.environ.get("CAMPUSPILOT_ENCRYPTION_KEY") or os.environ.get("CAMPUSPILOT_SECRET_KEY") or "campuspilot-dev-secret-key"
    return Fernet(derive_key(raw_key)).decrypt(cipher_text.encode("utf-8")).decode("utf-8") if cipher_text else ""


def load_bound_account(user_id: str) -> tuple[str, str]:
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT campus_account, campus_password_encrypted FROM campus_accounts WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise RuntimeError("campus account is not bound")
    password = decrypt_password(row["campus_password_encrypted"])
    if not row["campus_account"] or not password:
        raise RuntimeError("campus account or password is empty")
    return row["campus_account"], password


def setup_driver(user_id: str) -> webdriver.Chrome:
    options = Options()
    options.add_argument(f"--user-data-dir={chrome_profile_path(user_id)}")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    try:
        driver = webdriver.Chrome(options=options)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"})
        return driver
    except WebDriverException as exc:
        emit(False, f"Failed to start browser: {exc}", None, 1)


def find_first(driver: webdriver.Chrome, selectors: list[tuple[str, str]]) -> Any | None:
    for by, value in selectors:
        try:
            items = driver.find_elements(by, value)
            if items:
                return items[0]
        except Exception:
            pass
    return None


def set_input_value(driver: webdriver.Chrome, element: Any, value: str) -> None:
    element.click()
    element.send_keys(Keys.CONTROL, "a")
    element.send_keys(Keys.BACKSPACE)
    driver.execute_script(
        """
        const el = arguments[0];
        const value = arguments[1];
        el.value = value;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        element,
        value,
    )


def submit_cas_login(driver: webdriver.Chrome, username: str, password: str) -> None:
    user_el = WebDriverWait(driver, 30).until(lambda d: find_first(d, [(By.ID, "username"), (By.NAME, "username")]))
    pwd_el = find_first(driver, [(By.ID, "password"), (By.NAME, "password")])
    if pwd_el is None:
        raise RuntimeError("CAS password input not found")
    set_input_value(driver, user_el, username)
    set_input_value(driver, pwd_el, password)


    btn = find_first(driver, [(By.ID, "login-submit"), (By.CSS_SELECTOR, "button[type='submit']"), (By.CSS_SELECTOR, "input[type='submit']")])
    if btn is not None:
        btn.click()
    else:
        pwd_el.submit()


def is_cas_login_page(driver: webdriver.Chrome) -> bool:
    return "authserver" in driver.current_url or find_first(driver, [(By.ID, "username"), (By.NAME, "username")]) is not None


def is_webvpn_login_portal(driver: webdriver.Chrome) -> bool:
    return "frontend_static/frontend/login" in driver.current_url or "rump_frontend/login" in driver.current_url


def trigger_webvpn_login_page(driver: webdriver.Chrome) -> None:
    urls = [WEBVPN_BASE, LIBRARY_SSO_URL, JWC_MAIN_URL]
    for url in urls:
        safe_get(driver, url, 60)
        time.sleep(2)
        click_rump_redirect(driver)
        print(json.dumps({"status": "webvpn_login_probe", "url": url, "current_url": driver.current_url, "cas_login": is_cas_login_page(driver), "webvpn_portal": is_webvpn_login_portal(driver)}, ensure_ascii=False), file=sys.stderr)
        if is_cas_login_page(driver):
            return
        if "webvpn.njfu.edu.cn" in driver.current_url and driver.current_url not in (WEBVPN_BASE, WEBVPN_BASE + "/") and not is_webvpn_login_portal(driver):
            return


def has_webvpn_auth_cookie(driver: webdriver.Chrome) -> bool:
    expected_names = {"my_vpn_ticket", "my_client_ticket", "iPlanetDirectoryPro"}
    try:
        cookies = driver.execute_cdp_cmd("Network.getAllCookies", {}).get("cookies", [])
    except Exception:
        cookies = []
    if not cookies:
        try:
            cookies = driver.get_cookies()
        except Exception:
            cookies = []
    return any(c.get("name") in expected_names and "njfu.edu.cn" in (c.get("domain") or "") for c in cookies)


def wait_webvpn_ready(driver: webdriver.Chrome, timeout: int) -> None:
    WebDriverWait(driver, timeout).until(lambda d: (
        has_webvpn_auth_cookie(d)
        or (
            "authserver/login" not in d.current_url
            and not is_webvpn_login_portal(d)
            and d.current_url not in (WEBVPN_BASE, WEBVPN_BASE + "/")
            and "webvpn.njfu.edu.cn" in d.current_url
        )
    ))


def auto_webvpn_login(driver: webdriver.Chrome, username: str, password: str) -> None:
    trigger_webvpn_login_page(driver)
    if is_cas_login_page(driver):
        print(json.dumps({"status": "auto_login_submit", "username": username, "current_url": driver.current_url}, ensure_ascii=False), file=sys.stderr)
        submit_cas_login(driver, username, password)
        time.sleep(3)
    else:
        print(json.dumps({"status": "auto_login_no_cas_page", "current_url": driver.current_url}, ensure_ascii=False), file=sys.stderr)

    try:
        wait_webvpn_ready(driver, TIMEOUT_SECONDS)
    except TimeoutException as exc:
        if is_cas_login_page(driver) or is_webvpn_login_portal(driver):
            raise RuntimeError("WebVPN/CAS login did not complete in time; please finish captcha/MFA/login in the opened browser window") from exc
        raise RuntimeError(f"WebVPN did not become ready after login probes; current_url={driver.current_url}") from exc

    print(json.dumps({"status": "webvpn_ready", "current_url": driver.current_url}, ensure_ascii=False), file=sys.stderr)

def safe_get(driver: webdriver.Chrome, url: str, timeout: int = 60) -> None:
    try:
        driver.set_page_load_timeout(timeout)
        driver.get(url)
    except TimeoutException:
        pass


def click_rump_redirect(driver: webdriver.Chrome) -> None:
    if "rump_frontend" not in driver.current_url:
        return
    link = find_first(driver, [(By.ID, "url"), (By.CSS_SELECTOR, "a#url")])
    if link:
        link.click()
        time.sleep(2)


def click_seat_entry(driver: webdriver.Chrome) -> None:
    before = set(driver.window_handles)
    entry = find_first(driver, [
        (By.CSS_SELECTOR, ".group-item-img-2"),
        (By.XPATH, "//*[contains(text(), '座位预约')]"),
        (By.XPATH, "//*[contains(text(), '空间预约')]"),
        (By.XPATH, "//a[contains(@href, 'seat') or contains(@href, 'reserve')]"),
    ])
    if not entry:
        return
    entry.click(); time.sleep(2)
    new_handles = list(set(driver.window_handles) - before)
    if new_handles:
        driver.switch_to.window(new_handles[-1])
    elif driver.window_handles:
        driver.switch_to.window(driver.window_handles[-1])
    time.sleep(3)


def warmup_sessions(driver: webdriver.Chrome) -> None:
    safe_get(driver, JWC_MAIN_URL, 60)
    time.sleep(2)
    safe_get(driver, LIBRARY_SSO_URL, 60)
    time.sleep(2)
    click_rump_redirect(driver)
    click_seat_entry(driver)
    print(json.dumps({"status": "resource_warmup", "current_url": driver.current_url}, ensure_ascii=False), file=sys.stderr)


def current_cookie_domain(driver: webdriver.Chrome) -> str:
    host = urlparse(driver.current_url).hostname or "webvpn.njfu.edu.cn"
    return ".njfu.edu.cn" if host.endswith("njfu.edu.cn") else host


def extract_cookies(driver: webdriver.Chrome) -> list[dict[str, str]]:
    all_cookies: list[dict[str, Any]] = []
    try:
        all_cookies.extend(driver.execute_cdp_cmd("Network.getAllCookies", {}).get("cookies", []))
    except Exception:
        pass
    try:
        all_cookies.extend(driver.get_cookies())
    except Exception:
        pass
    try:
        domain = current_cookie_domain(driver)
        for part in str(driver.execute_script("return document.cookie || '';" )).split(";"):
            if "=" in part:
                name, value = part.strip().split("=", 1)
                all_cookies.append({"name": name, "value": value, "domain": domain, "path": "/"})
    except Exception:
        pass

    result: list[dict[str, str]] = []
    seen = set()
    for c in all_cookies:
        name, domain = c.get("name", ""), c.get("domain", "") or "webvpn.njfu.edu.cn"
        if not name or "njfu.edu.cn" not in domain:
            continue
        key = (name, domain, c.get("path", "/"))
        if key in seen:
            continue
        seen.add(key)
        result.append({"name": name, "value": c.get("value", ""), "domain": domain, "path": c.get("path", "/")})
    print(json.dumps({"status": "cookies_extracted", "count": len(result), "names": [c["name"] for c in result]}, ensure_ascii=False), file=sys.stderr)
    return result


def save_cookies(cookies: list[dict[str, str]], path: Path) -> None:
    path.write_text("\n".join(f"{c['name']}={c['value']}|{c.get('domain', '')}|{c.get('path', '/')}" for c in cookies) + "\n", encoding="utf-8")


def update_database(user_id: str, cookie_file: Path) -> None:
    conn = sqlite3.connect(database_path())
    try:
        conn.execute("""
            UPDATE campus_accounts
            SET webvpn_cookie_path = ?, session_valid = 1,
                last_login_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (str(cookie_file), user_id))
        conn.commit()
    finally:
        conn.close()
    conn = sqlite3.connect(database_path())
    try:
        conn.execute("""
            INSERT INTO sessions (user_id, session_type, cookie_path, is_valid, last_checked_at)
            VALUES (?, 'webvpn', ?, 1, CURRENT_TIMESTAMP)
        """, (user_id, str(cookie_file)))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def main() -> None:
    if len(sys.argv) < 2:
        emit(False, "user_id is required", None, 1)
    user_id = sys.argv[1]
    status_file = Path(sys.argv[2]) if len(sys.argv) >= 3 else None
    cookie_file = cookie_path(user_id)
    driver = setup_driver(user_id)
    try:
        username, password = load_bound_account(user_id)
        auto_webvpn_login(driver, username, password)
        warmup_sessions(driver)
        cookies = extract_cookies(driver)
        if not cookies:
            emit(False, "no cookies found after login", None, 1)
        save_cookies(cookies, cookie_file)
        update_database(user_id, cookie_file)
        success_data = {"status": "completed", "cookie_count": len(cookies), "cookie_file": str(cookie_file), "chrome_profile": str(chrome_profile_path(user_id)), "final_url": driver.current_url}
        write_status_file(status_file, {"success": True, "message": "interactive login completed", "data": success_data})
        time.sleep(10)
        emit(True, "interactive login completed", success_data, 0)
    except Exception as exc:
        emit(False, f"unexpected error: {exc}", None, 1)
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
