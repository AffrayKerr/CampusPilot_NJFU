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
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
except ImportError:
    print(json.dumps({
        "success": False,
        "message": "selenium is not installed. Run: pip install selenium",
        "data": None
    }, ensure_ascii=False))
    sys.exit(1)

WEBVPN_BASE = "https://webvpn.njfu.edu.cn"
TIMEOUT_SECONDS = 600


def emit(success: bool, message: str, data: Any = None, code: int = 0) -> None:
    payload = {"success": success, "message": message, "data": data}
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(code)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def cookie_path(user_id: str) -> Path:
    runtime_dir = project_root() / "runtime" / "users" / user_id
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir / "webvpn.cookie"


def setup_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
        return driver
    except WebDriverException as e:
        if "chromedriver" in str(e).lower() or "chrome" in str(e).lower():
            emit(False, "Chrome or ChromeDriver not found. Please install Chrome browser.", None, 1)
        else:
            emit(False, f"Failed to start browser: {str(e)}", None, 1)


def wait_for_login(driver: webdriver.Chrome, timeout: int) -> bool:
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: "frontend_static/frontend/login/index.html" in d.current_url
            or "rump_frontend" not in d.current_url and WEBVPN_BASE in d.current_url
        )
        return True
    except TimeoutException:
        return False


def extract_cookies(driver: webdriver.Chrome) -> list[dict[str, str]]:
    all_cookies = driver.get_cookies()
    njfu_cookies = []
    for cookie in all_cookies:
        domain = cookie.get("domain", "")
        if "njfu.edu.cn" in domain:
            njfu_cookies.append({
                "name": cookie["name"],
                "value": cookie["value"],
                "domain": domain
            })
    return njfu_cookies


def save_cookies(cookies: list[dict[str, str]], path: Path) -> None:
    lines = [f"{c['name']}={c['value']}" for c in cookies]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if len(sys.argv) < 2:
        emit(False, "user_id is required", None, 1)
    
    user_id = sys.argv[1]
    cookie_file = cookie_path(user_id)
    
    driver = setup_driver()
    
    try:
        driver.get(WEBVPN_BASE)
        
        current_url = driver.current_url
        if "frontend_static/frontend/login/index.html" in current_url:
            emit(True, "already logged in, cookies extracted", {"cookie_file": str(cookie_file)}, 0)
        
        print(json.dumps({
            "status": "waiting",
            "message": f"Please complete login in the browser window (timeout: {TIMEOUT_SECONDS}s)",
            "current_url": current_url
        }, ensure_ascii=False), file=sys.stderr)
        
        if not wait_for_login(driver, TIMEOUT_SECONDS):
            emit(False, f"login timeout after {TIMEOUT_SECONDS} seconds", None, 1)
        
        time.sleep(2)
        
        cookies = extract_cookies(driver)
        
        if not cookies:
            emit(False, "no cookies found after login", None, 1)
        
        save_cookies(cookies, cookie_file)
        
        emit(True, "interactive login completed", {
            "cookie_count": len(cookies),
            "cookie_file": str(cookie_file),
            "final_url": driver.current_url
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
