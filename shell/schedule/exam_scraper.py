#!/usr/bin/env python3
"""Independent exam arrangement scraper for JWC through WebVPN."""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

JWC_BASE = (
    "https://webvpn.njfu.edu.cn/webvpn/LjIwMS4xNjkuMjE4LjE2OC4xNjc=/"
    "LjIwMy4xNzIuMjIyLjE3Mi45OC4xNjMuMjA2LjE1My4yMTguOTYuMTU3LjE1Ni4yMTkuMTAwLjE1NC4yMTA="
)
JWC_MAIN = f"{JWC_BASE}/jsxsd/framework/xsMainV.jsp?vpn-0"
EXAM_QUERY_URLS = [
    f"{JWC_BASE}/jsxsd/xsks/xsksap_query",
    f"{JWC_BASE}/jsxsd/xsks/xsksap_query.do",
]
EXAM_URL = f"{JWC_BASE}/jsxsd/xsks/xsksap_list"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def emit(success: bool, message: str, data: Any = None) -> None:
    print(json.dumps({"success": success, "message": message, "data": data}, ensure_ascii=False))
    sys.exit(0 if success else 1)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def database_path() -> Path:
    return Path(os.environ.get("DATABASE_PATH") or project_root() / "database" / "campuspilot.db")


def user_runtime_dir(user_id: str) -> Path:
    return Path(os.environ.get("USERS_RUNTIME_DIR") or project_root() / "runtime" / "users") / user_id


def cookie_path(user_id: str) -> Path:
    return user_runtime_dir(user_id) / "webvpn.cookie"


def chrome_profile_path(user_id: str) -> Path:
    return user_runtime_dir(user_id) / "chrome_profile"


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def resolve_user_pk(conn: sqlite3.Connection, user_id: str) -> int:
    if user_id.isdigit():
        return int(user_id)
    row = conn.execute("SELECT id FROM users WHERE username = ?", (user_id,)).fetchone()
    if row is None:
        raise RuntimeError(f"user not found: {user_id!r}")
    return row["id"]


def save_exams(user_id: str, exams: list[dict[str, str]]) -> None:
    conn = db_connect()
    uid = resolve_user_pk(conn, user_id)
    settings = conn.execute(
        "SELECT exam_default_reminders FROM notification_settings WHERE user_id = ?",
        (uid,),
    ).fetchone()
    try:
        default_reminders = json.loads(settings["exam_default_reminders"] or "[1440, 120]") if settings else [1440, 120]
    except (TypeError, json.JSONDecodeError):
        default_reminders = [1440, 120]

    conn.execute("DELETE FROM reminders WHERE user_id = ? AND target_type = 'exam'", (uid,))
    conn.execute("DELETE FROM exams WHERE user_id = ?", (uid,))
    for exam in exams:
        cursor = conn.execute(
            "INSERT INTO exams (user_id, course_name, exam_time, exam_location, seat_number) VALUES (?, ?, ?, ?, ?)",
            (uid, exam["course_name"], exam["exam_time"], exam["exam_location"], exam["seat_number"]),
        )
        exam_id = cursor.lastrowid
        for minutes in default_reminders:
            try:
                remind_before_minutes = int(minutes)
            except (TypeError, ValueError):
                continue
            if remind_before_minutes <= 0:
                continue
            conn.execute(
                "INSERT INTO reminders (user_id, target_type, target_id, remind_before_minutes, enabled) VALUES (?, 'exam', ?, ?, 1)",
                (uid, exam_id, remind_before_minutes),
            )
    conn.commit()
    conn.close()

def load_session(user_id: str) -> requests.Session:
    path = cookie_path(user_id)
    if not path.is_file():
        raise RuntimeError("webvpn cookie not found; please login first via bind-interactive")
    session = requests.Session()
    session.trust_env = False
    session.verify = False
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"})
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name_value, domain = (line.split("|", 1) + ["webvpn.njfu.edu.cn"])[:2] if "|" in line else (line, "webvpn.njfu.edu.cn")
        if "=" not in name_value:
            continue
        name, value = name_value.split("=", 1)
        session.cookies.set(name, value, domain=domain.split("|", 1)[0] or "webvpn.njfu.edu.cn")
        session.cookies.set(name, value, domain=".njfu.edu.cn")
    session.get(JWC_MAIN, timeout=10, allow_redirects=True)
    return session


def check_session_valid(response: requests.Response) -> None:
    invalid_markers = (
        "统一身份认证",
        "casLoginForm",
        "rump_frontend/login",
        "authserver/login",
    )
    if any(marker in response.text for marker in invalid_markers) or any(marker in response.url for marker in invalid_markers):
        raise RuntimeError("session expired; please re-login via bind-interactive")

def current_term_id(today: date | None = None) -> str:
    today = today or date.today()
    if today.month >= 9:
        return f"{today.year}-{today.year + 1}-1"
    return f"{today.year - 1}-{today.year}-2"


def choose_option(select: Any) -> str:
    options = select.find_all("option")
    name = (select.get("name") or "").lower()
    option_values = [(option.get("value", ""), option.get_text(" ", strip=True)) for option in options]

    if any(key in name for key in ("xnxq", "xnxqid", "xq")):
        current_term = current_term_id()
        for value, text in option_values:
            if value == current_term or current_term in text:
                return value
        for value, text in option_values:
            if "2025-2026-2" in value or "2025-2026-2" in text:
                return value

    for keyword in ("新庄校区", "未考试"):
        for value, text in option_values:
            if keyword in text and value:
                return value
    for value, _text in option_values:
        if value:
            return value
    return ""


def extract_query_params(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    params: dict[str, str] = {}
    for field in soup.find_all(["input", "select"]):
        name = field.get("name")
        if not name:
            continue
        if field.name == "select":
            params[name] = choose_option(field)
        elif field.get("type", "").lower() in {"hidden", "text"}:
            params[name] = field.get("value", "")
    params.setdefault("xqlbmc", "")
    return params


def fetch_exam_html(session: requests.Session) -> str:
    last_error: Exception | None = None
    for query_url in EXAM_QUERY_URLS:
        try:
            query_resp = session.get(query_url, timeout=10)
            query_resp.raise_for_status()
            check_session_valid(query_resp)
            params = extract_query_params(query_resp.text)
            list_resp = session.post(EXAM_URL, data=params, headers={"Referer": query_url}, timeout=10)
            list_resp.raise_for_status()
            check_session_valid(list_resp)
            return list_resp.text
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"exam query failed: {last_error}")


def load_cookie_pairs(user_id: str) -> list[tuple[str, str, str]]:
    path = cookie_path(user_id)
    if not path.is_file():
        raise RuntimeError("webvpn cookie not found; please login first via bind-interactive")
    pairs: list[tuple[str, str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            parts = line.split("|")
            name_value = parts[0]
            domain = parts[1] if len(parts) > 1 and parts[1] else ".njfu.edu.cn"
        else:
            name_value = line
            domain = ".njfu.edu.cn"
        if "=" in name_value:
            name, value = name_value.split("=", 1)
            pairs.append((name, value, domain))
    return pairs


def inject_cookies(driver: Any, user_id: str) -> None:
    driver.get("https://webvpn.njfu.edu.cn")
    for name, value, domain in load_cookie_pairs(user_id):
        try:
            driver.add_cookie({"name": name, "value": value, "domain": domain.strip(), "path": "/", "secure": True})
        except Exception:
            pass


def select_native_exam_option(driver: Any, By: Any, Select: Any) -> bool:
    selected = False
    current_term = current_term_id()
    for select_el in driver.find_elements(By.TAG_NAME, "select"):
        select_name = (select_el.get_attribute("name") or "").lower()
        options = select_el.find_elements(By.TAG_NAME, "option")
        options_text = [option.text.strip() for option in options]

        if any(key in select_name for key in ("xnxq", "xnxqid", "xq")):
            target = next((text for text in options_text if current_term in text), "")
            if target:
                Select(select_el).select_by_visible_text(target)
                selected = True
            continue

        target = next((text for text in options_text if "新庄校区" in text), "")
        if not target:
            target = next((text for text in options_text if "未考试" in text), "")
        if target:
            Select(select_el).select_by_visible_text(target)
            selected = True
    return selected

def select_custom_exam_option(driver: Any, By: Any, WebDriverWait: Any, timeout: int) -> bool:
    dropdown_triggers = driver.find_elements(
        By.XPATH,
        "//*[contains(@class,'el-select') or contains(@class,'el-input') or contains(@class,'select')]"
        "[.//*[contains(text(),'请选择') or contains(text(),'--请选择--')] or contains(.,'请选择') or contains(.,'--请选择--')]",
    )
    if not dropdown_triggers:
        dropdown_triggers = driver.find_elements(By.XPATH, "//*[contains(text(),'--请选择--') or contains(text(),'请选择')]")

    for trigger in dropdown_triggers:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", trigger)
            driver.execute_script("arguments[0].click();", trigger)
            time.sleep(0.5)
            option = WebDriverWait(driver, min(timeout, 5)).until(
                lambda d: next(
                    (
                        el for el in d.find_elements(By.XPATH, "//*[contains(@class,'el-select-dropdown') or contains(@class,'dropdown') or contains(@class,'option') or self::li or self::span]")
                        if el.is_displayed() and ("新庄校区" in el.text or "未考试" in el.text)
                    ),
                    None,
                )
            )
            driver.execute_script("arguments[0].click();", option)
            return True
        except Exception:
            continue
    return False


def click_exam_query_button(driver: Any, By: Any) -> bool:
    candidates = driver.find_elements(
        By.XPATH,
        "//button[contains(.,'查询')]|//input[contains(@value,'查询')]|//a[contains(.,'查询')]|//*[contains(@class,'button') and contains(.,'查询')]",
    )
    for button in candidates:
        try:
            if not button.is_displayed():
                continue
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", button)
            driver.execute_script("arguments[0].click();", button)
            time.sleep(2)
            return True
        except Exception:
            continue
    return False


def debug_exam_html_path(user_id: str) -> Path:
    path = user_runtime_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    return path / "exam_result.html"


def save_debug_exam_html(user_id: str, html: str) -> None:
    try:
        debug_exam_html_path(user_id).write_text(html, encoding="utf-8")
    except Exception as exc:
        print(json.dumps({"status": "exam_debug_html_save_failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr, flush=True)


def submit_exam_query_directly(driver: Any, xqlb: str = "1") -> None:
    if not extract_query_params(driver.page_source).get("xnxqid"):
        driver.get(EXAM_QUERY_URLS[0])
        time.sleep(1)
    params = extract_query_params(driver.page_source)
    params["xnxqid"] = current_term_id()
    params["xqlb"] = xqlb
    params.setdefault("kw0401id", "")
    params.setdefault("xqlbmc", "")
    if not params.get("xqlb"):
        params["xqlb"] = "1"
    driver.execute_script(
        """
        const action = arguments[0];
        const params = arguments[1];
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = action;
        for (const [name, value] of Object.entries(params)) {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = name;
            input.value = value == null ? '' : String(value);
            form.appendChild(input);
        }
        document.body.appendChild(form);
        form.submit();
        """,
        EXAM_URL,
        params,
    )
    time.sleep(2)

def fetch_exam_html_with_browser(user_id: str) -> str:
    try:
        from selenium import webdriver
        from selenium.common.exceptions import TimeoutException, WebDriverException
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
    except ImportError as exc:
        raise RuntimeError("selenium is required for exam sync; run: pip install selenium") from exc

    profile_path = chrome_profile_path(user_id)
    if not profile_path.exists():
        raise RuntimeError("WebVPN 会话无效，请先在个人中心重新绑定/登录校园网账号")

    timeout = int(os.environ.get("EXAM_BROWSER_TIMEOUT", "15"))
    options = Options()
    options.page_load_strategy = "eager"
    options.add_argument(f"--user-data-dir={profile_path}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    if os.environ.get("SCHEDULE_HEADLESS", "0") == "1":
        options.add_argument("--headless=new")
    else:
        options.add_argument("--window-position=-2400,-2400")
        options.add_argument("--window-size=1280,800")

    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as exc:
        raise RuntimeError(f"failed to start Chrome/ChromeDriver: {exc}") from exc

    try:
        driver.set_page_load_timeout(timeout)
        inject_cookies(driver, user_id)
        try:
            driver.get(JWC_MAIN)
        except TimeoutException:
            pass
        try:
            WebDriverWait(driver, 3).until(lambda d: "authserver/login" not in d.current_url)
        except TimeoutException:
            pass

        loaded = False
        for url in EXAM_QUERY_URLS:
            try:
                driver.get(url)
            except TimeoutException:
                pass
            if "考试安排查询" in driver.page_source or "考试名称" in driver.page_source:
                loaded = True
                break
        if not loaded:
            raise RuntimeError("WebVPN 会话无效，请先在个人中心重新绑定/登录校园网账号")

        selected = select_native_exam_option(driver, By, Select)
        if not selected:
            selected = select_custom_exam_option(driver, By, WebDriverWait, timeout)
        print(json.dumps({"status": "exam_option_selected", "selected": selected}, ensure_ascii=False), file=sys.stderr, flush=True)

        html = ""
        for exam_type in ("1", "2", "3"):
            submit_exam_query_directly(driver, exam_type)
            try:
                WebDriverWait(driver, 8).until(lambda d: "dataList" in d.page_source or len(d.find_elements(By.XPATH, "//table//tr")) > 1)
            except TimeoutException:
                pass

            html = driver.page_source
            exams = parse_exams(html)
            print(
                json.dumps(
                    {
                        "status": "exam_category_result",
                        "xqlb": exam_type,
                        "count": len(exams),
                        "url": driver.current_url,
                        "html_length": len(html),
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
                flush=True,
            )
            if exams:
                break

        save_debug_exam_html(user_id, html)
        print(json.dumps({"status": "exam_result_page", "url": driver.current_url, "html_length": len(html), "debug_html": str(debug_exam_html_path(user_id))}, ensure_ascii=False), file=sys.stderr, flush=True)
        return html
    finally:
        driver.quit()


def parse_exams(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")

    keywords = ("\u8bfe\u7a0b", "\u540d\u79f0", "\u8003\u8bd5", "\u65f6\u95f4", "\u6821\u533a", "\u8003\u573a", "\u5730\u70b9", "\u5ea7\u4f4d", "\u5ea7\u53f7")
    empty_keywords = ("\u6682\u65e0", "\u6ca1\u6709", "\u65e0\u6570\u636e")
    course_header = "\u8bfe\u7a0b\u540d\u79f0"
    time_header = "\u8003\u8bd5\u65f6\u95f4"

    def normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()

    def build_exam(values: list[str], course_idx: int, time_idx: int, location_idx: int | None, seat_idx: int | None) -> dict[str, str] | None:
        if course_idx >= len(values) or time_idx >= len(values):
            return None
        row_text = "".join(values)
        if any(keyword in row_text for keyword in empty_keywords):
            return None
        course_name = values[course_idx]
        exam_time = values[time_idx]
        if not course_name or course_name in {course_header, "&nbsp;"}:
            return None
        if not exam_time or exam_time == time_header:
            return None
        return {
            "course_name": course_name,
            "exam_time": exam_time,
            "exam_location": values[location_idx] if location_idx is not None and location_idx < len(values) else "",
            "seat_number": values[seat_idx] if seat_idx is not None and seat_idx < len(values) else "",
        }

    def find_col(headers: list[str], *keys: str) -> int | None:
        for idx, header in enumerate(headers):
            compact = header.replace(" ", "")
            if all(key in compact for key in keys):
                return idx
        return None

    def parse_fixed_data_list(table: Any) -> list[dict[str, str]]:
        parsed: list[dict[str, str]] = []
        for row in table.find_all("tr"):
            values = [normalize(c.get_text(" ", strip=True)) for c in row.find_all("td")]
            if len(values) < 8:
                continue
            exam = build_exam(values, 5, 7, 8, 9)
            if exam:
                parsed.append(exam)
        return parsed

    def parse_table_by_header(table: Any) -> list[dict[str, str]]:
        rows = table.find_all("tr")
        if not rows:
            return []

        header_index = -1
        header_score = -1
        for idx, row in enumerate(rows):
            cells = [normalize(c.get_text(" ", strip=True)) for c in row.find_all(["th", "td"])]
            if not cells:
                continue
            row_text = "".join(cells)
            score = sum(1 for keyword in keywords if keyword in row_text)
            if score > header_score:
                header_index = idx
                header_score = score

        if header_index < 0 or header_score < 2:
            return []

        headers = [normalize(c.get_text(" ", strip=True)) for c in rows[header_index].find_all(["th", "td"])]
        course_idx = find_col(headers, "\u8bfe\u7a0b", "\u540d\u79f0")
        if course_idx is None:
            course_idx = find_col(headers, "\u8bfe\u7a0b")
        time_idx = find_col(headers, "\u8003\u8bd5", "\u65f6\u95f4")
        if time_idx is None:
            time_idx = find_col(headers, "\u65f6\u95f4")
        location_idx = find_col(headers, "\u8003\u573a")
        if location_idx is None:
            location_idx = find_col(headers, "\u5730\u70b9")
        if location_idx is None:
            location_idx = find_col(headers, "\u6821\u533a")
        seat_idx = find_col(headers, "\u5ea7\u4f4d")
        if seat_idx is None:
            seat_idx = find_col(headers, "\u5ea7\u53f7")

        if course_idx is None and len(headers) > 5:
            course_idx = 5
        if time_idx is None and len(headers) > 7:
            time_idx = 7
        if location_idx is None and len(headers) > 8:
            location_idx = 8
        if seat_idx is None and len(headers) > 9:
            seat_idx = 9
        if course_idx is None or time_idx is None:
            return []

        parsed: list[dict[str, str]] = []
        for row in rows[header_index + 1:]:
            values = [normalize(c.get_text(" ", strip=True)) for c in row.find_all("td")]
            if not values:
                continue
            exam = build_exam(values, course_idx, time_idx, location_idx, seat_idx)
            if exam:
                parsed.append(exam)
        return parsed

    data_list = soup.find("table", {"id": "dataList"})
    if data_list:
        fixed_exams = parse_fixed_data_list(data_list)
        if fixed_exams:
            return fixed_exams

    tables = soup.find_all("table")
    table_candidates = sorted(
        tables,
        key=lambda table: (0 if table.get("id") == "dataList" else 1, -len(table.get_text(" ", strip=True))),
    )
    for table in table_candidates:
        exams = parse_table_by_header(table)
        if exams:
            return exams
    return []

def sync_exam(user_id: str) -> None:
    source = "requests"
    exams: list[dict[str, str]] = []
    try:
        session = load_session(user_id)
        html = fetch_exam_html(session)
        save_debug_exam_html(user_id, html)
        exams = parse_exams(html)
        print(json.dumps({"status": "exam_parse_result", "source": "requests", "count": len(exams), "html_length": len(html), "debug_html": str(debug_exam_html_path(user_id))}, ensure_ascii=False), file=sys.stderr, flush=True)
    except Exception as exc:
        print(json.dumps({"status": "exam_requests_failed", "error": str(exc), "fallback_to_browser": True}, ensure_ascii=False), file=sys.stderr, flush=True)

    if not exams:
        source = "selenium"
        html = fetch_exam_html_with_browser(user_id)
        exams = parse_exams(html)
        print(json.dumps({"status": "exam_parse_result", "source": "selenium", "count": len(exams), "html_length": len(html), "debug_html": str(debug_exam_html_path(user_id))}, ensure_ascii=False), file=sys.stderr, flush=True)

    save_exams(user_id, exams)
    emit(True, f"synced {len(exams)} exams", {"count": len(exams), "source": source})

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["sync_exam"])
    parser.add_argument("user_id")
    args = parser.parse_args()
    try:
        sync_exam(args.user_id)
    except Exception as exc:
        emit(False, str(exc), None)


if __name__ == "__main__":
    main()
