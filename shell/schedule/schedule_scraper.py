#!/usr/bin/env python3
"""Schedule and exam scraper for JWC (教务管理系统) through WebVPN."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

JWC_BASE = (
    "https://webvpn.njfu.edu.cn/webvpn/LjIwMS4xNjkuMjE4LjE2OC4xNjc=/"
    "LjIwMy4xNzIuMjIyLjE3Mi45OC4xNjMuMjA2LjE1My4yMTguOTYuMTU3LjE1Ni4yMTkuMTAwLjE1NC4yMTA="
)
JWC_MAIN = f"{JWC_BASE}/jsxsd/framework/xsMainV.jsp?vpn-0"
SCHEDULE_LIST_URL = f"{JWC_BASE}/jsxsd/xskb/xskb_list.do"
SCHEDULE_PRINT_URL = f"{JWC_BASE}/jsxsd/xskb/xskb_print.do?vpn-0"
EXAM_QUERY_URL = f"{JWC_BASE}/jsxsd/xsks/xsksap_query"
EXAM_QUERY_URL_FALLBACK = f"{JWC_BASE}/jsxsd/xsks/xsksap_query.do"
EXAM_URL = f"{JWC_BASE}/jsxsd/xsks/xsksap_list"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def emit(success: bool, message: str, data: Any = None) -> None:
    print(json.dumps({"success": success, "message": message, "data": data}, ensure_ascii=False))
    sys.exit(0 if success else 1)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def database_path() -> Path:
    env_path = os.environ.get("DATABASE_PATH")
    if env_path:
        return Path(env_path)
    return project_root() / "database" / "campuspilot.db"


def user_runtime_dir(user_id: str) -> Path:
    runtime_base = os.environ.get("USERS_RUNTIME_DIR") or str(project_root() / "runtime" / "users")
    return Path(runtime_base) / user_id


def cookie_path(user_id: str) -> Path:
    return user_runtime_dir(user_id) / "webvpn.cookie"


def chrome_profile_path(user_id: str) -> Path:
    return user_runtime_dir(user_id) / "chrome_profile"


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def load_session(user_id: str) -> requests.Session:
    path = cookie_path(user_id)
    if not path.is_file():
        raise RuntimeError("webvpn cookie not found; please login first via bind-interactive")

    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            name_value, domain = line.split("|", 1)[0], line.split("|", 1)[1].split("|")[0]
            if "=" not in name_value:
                continue
            name, value = name_value.split("=", 1)
            session.cookies.set(name, value, domain=domain)
        elif "=" in line:
            name, value = line.split("=", 1)
            session.cookies.set(name, value, domain="webvpn.njfu.edu.cn")
            session.cookies.set(name, value, domain=".njfu.edu.cn")

    # Visit JWC main page first to establish JWC internal session via WebVPN SSO
    main_resp = session.get(JWC_MAIN, timeout=30, allow_redirects=True)
    if main_resp.ok:
        save_current_week(user_id, parse_current_week(main_resp.text))

    return session


def check_session_valid(response: requests.Response) -> None:
    if "统一身份认证" in response.text or "casLoginForm" in response.text:
        raise RuntimeError("session expired; please re-login via bind-interactive")
    if "rump_frontend/login" in response.url:
        raise RuntimeError("session expired; redirected to webvpn login page")


def extract_schedule_params(html: str) -> dict[str, str]:
    """Extract kbjcmsid and xnxq01id from schedule list page."""
    soup = BeautifulSoup(html, "html.parser")
    params: dict[str, str] = {}

    for select_name in ("xnxq01id", "kbjcmsid"):
        tag = soup.find("select", {"name": select_name})
        if tag:
            selected = tag.find("option", selected=True) or tag.find("option")
            if selected:
                value = selected.get("value", "")
                if value:
                    params[select_name] = value

    for hidden in soup.find_all("input", {"type": "hidden"}):
        name = hidden.get("name", "")
        value = hidden.get("value", "")
        if name in ("kbjcmsid", "xnxq01id") and value and name not in params:
            params[name] = value

    patterns = {
        "kbjcmsid": [
            r"kbjcmsid=([A-Za-z0-9]+)",
            r"kbjcmsid['\"]?\s*[:=]\s*['\"]([A-Za-z0-9]+)['\"]",
            r"name=['\"]kbjcmsid['\"][^>]*value=['\"]([^'\"]+)['\"]",
        ],
        "xnxq01id": [
            r"xnxq01id=([0-9]{4}-[0-9]{4}-[0-9])",
            r"xnxq01id['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]",
            r"name=['\"]xnxq01id['\"][^>]*value=['\"]([^'\"]+)['\"]",
        ],
    }
    for key, key_patterns in patterns.items():
        if params.get(key):
            continue
        for pattern in key_patterns:
            match = re.search(pattern, html, re.I)
            if match:
                params[key] = match.group(1).replace("&amp;", "&")
                break

    if "xnxq01id" not in params:
        option = soup.select_one("select[name=xnxq01id] option[selected], select[name=xnxq01id] option")
        if option and option.get("value"):
            params["xnxq01id"] = option.get("value", "")

    return params


def fetch_schedule_html(session: requests.Session) -> tuple[str, dict[str, str]]:
    """Two-step fetch: GET list page for params, POST print endpoint for data."""
    list_resp = session.get(SCHEDULE_LIST_URL, timeout=30)
    list_resp.raise_for_status()
    check_session_valid(list_resp)
    
    params = extract_schedule_params(list_resp.text)
    if not params.get("kbjcmsid"):
        return list_resp.text, params
    
    print_resp = session.post(SCHEDULE_PRINT_URL, params={
        "xnxq01id": params.get("xnxq01id", ""),
        "zc": "",
        "kbjcmsid": params["kbjcmsid"],
        "wkbkc": "1",
    }, timeout=30)
    print_resp.raise_for_status()
    return print_resp.text, params


def extract_exam_query_params(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    params: dict[str, str] = {}

    for field in soup.find_all(["input", "select"]):
        name = field.get("name")
        if not name:
            continue
        if field.name == "select":
            selected = field.find("option", selected=True) or field.find("option")
            params[name] = selected.get("value", "") if selected else ""
        elif field.get("type", "").lower() in {"hidden", "text"}:
            params[name] = field.get("value", "")

    term_select = soup.find("select", {"name": re.compile(r"xnxq|xq|term", re.I)})
    if term_select and term_select.get("name"):
        selected = term_select.find("option", selected=True) or term_select.find("option")
        if selected and selected.get("value"):
            params[term_select["name"]] = selected["value"]

    exam_select = soup.find("select", {"name": re.compile(r"ks|exam", re.I)})
    if exam_select and exam_select.get("name"):
        options = exam_select.find_all("option")
        chosen = None
        for option in options:
            text = option.get_text(" ", strip=True)
            if "新庄校区" in text:
                chosen = option
                break
        if not chosen:
            for option in options:
                text = option.get_text(" ", strip=True)
                if "未考试" in text:
                    chosen = option
                    break
        if not chosen and len(options) > 1:
            chosen = options[1]
        if chosen and chosen.get("value"):
            params[exam_select["name"]] = chosen["value"]

    params.setdefault("xqlbmc", "")
    return params


def fetch_exam_html(session: requests.Session) -> str:
    try:
        query_resp = session.get(EXAM_QUERY_URL, timeout=30)
        query_resp.raise_for_status()
    except requests.RequestException:
        query_resp = session.get(EXAM_QUERY_URL_FALLBACK, timeout=30)
        query_resp.raise_for_status()
    check_session_valid(query_resp)

    params = extract_exam_query_params(query_resp.text)
    headers = {"Referer": EXAM_QUERY_URL}
    list_resp = session.post(EXAM_URL, data=params, headers=headers, timeout=30)
    list_resp.raise_for_status()
    check_session_valid(list_resp)
    return list_resp.text


def parse_schedule(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    courses: list[dict[str, Any]] = []

    table = soup.find("table", {"id": "timetable"})
    if not table:
        return courses

    for row in table.find_all("tr"):
        # section name is in <th>, course cells are in <td>
        th = row.find("th")
        cells = row.find_all("td")
        if not th or not cells or len(cells) < 7:
            continue

        section = th.get_text(strip=True).replace("\xa0", "").strip()
        if not section or section.startswith("星期") or section == "&nbsp;":
            continue

        for weekday, cell in enumerate(cells[:7], start=1):
            # use the visible kbcontent div (kbcontent1 is the compact view, kbcontent is the detailed view)
            for div in cell.find_all("div", class_="kbcontent"):
                # split multiple courses within one cell by the separator line
                raw_html = str(div)
                blocks = re.split(r"-{5,}", div.get_text(separator="\n"))
                for block in blocks:
                    lines = [ln.strip() for ln in block.split("\n") if ln.strip() and ln.strip() != "\xa0"]
                    if len(lines) < 2:
                        continue

                    course_name = lines[0]
                    if not course_name or course_name == "\xa0":
                        continue

                    week_info = ""
                    teacher = ""
                    classroom = ""

                    for line in lines[1:]:
                        if re.search(r"\d+.*[周节]|单周|双周|\(周\)", line):
                            week_info = line
                        elif re.search(r"\d{4,}|[A-Z]\d+|阶\d*|教室|楼|馆|校区", line) and not classroom:
                            classroom = line
                        elif not teacher and line != course_name and not re.search(r"\d{4,}|\(周\)|周\]", line):
                            teacher = line

                    courses.append({
                        "course_name": course_name,
                        "teacher": teacher,
                        "week_info": week_info,
                        "weekday": weekday,
                        "section": section,
                        "classroom": classroom,
                    })

    return courses


def parse_exams(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    exams: list[dict[str, Any]] = []

    table = soup.find("table", {"id": "dataList"}) or soup.find("table", class_=re.compile(r"(?:table|datelist|dataList)", re.I))
    if not table:
        return exams

    rows = table.find_all("tr")
    if not rows:
        return exams

    header_cells = rows[0].find_all(["th", "td"])
    headers = [cell.get_text(" ", strip=True).replace("\xa0", "") for cell in header_cells]

    def find_col(*keywords: str) -> int | None:
        for idx, header in enumerate(headers):
            if all(keyword in header for keyword in keywords):
                return idx
        return None

    course_idx = find_col("课程", "名称") or find_col("课程")
    time_idx = find_col("考试", "时间") or find_col("时间")
    location_idx = find_col("考场") or find_col("地点") or find_col("校区")
    seat_idx = find_col("座位") or find_col("座号")

    if course_idx is None:
        course_idx = 5 if len(headers) > 5 else 0
    if time_idx is None:
        time_idx = 7 if len(headers) > 7 else 1
    if location_idx is None:
        location_idx = 8 if len(headers) > 8 else 2
    if seat_idx is None:
        seat_idx = 9 if len(headers) > 9 else None

    for row in rows[1:]:
        cells = row.find_all("td")
        if not cells:
            continue
        values = [cell.get_text(" ", strip=True).replace("\xa0", " ").strip() for cell in cells]
        if course_idx >= len(values) or time_idx >= len(values):
            continue

        course_name = values[course_idx]
        exam_time = values[time_idx]
        if not course_name or course_name in {"课程名称", "&nbsp;"}:
            continue

        exams.append({
            "course_name": course_name,
            "exam_time": exam_time,
            "exam_location": values[location_idx] if location_idx < len(values) else "",
            "seat_number": values[seat_idx] if seat_idx is not None and seat_idx < len(values) else "",
        })

    return exams


def resolve_user_pk(conn: sqlite3.Connection, user_id: str) -> int:
    """Resolve user_id string to users.id integer.

    Accepts either a numeric string (already an integer PK) or a username.
    """
    if user_id.isdigit():
        return int(user_id)
    row = conn.execute("SELECT id FROM users WHERE username = ?", (user_id,)).fetchone()
    if row is None:
        raise RuntimeError(f"user not found: {user_id!r}")
    return row["id"]


def save_schedules(user_id: str, courses: list[dict[str, Any]]) -> None:
    conn = db_connect()
    uid = resolve_user_pk(conn, user_id)
    conn.execute("DELETE FROM schedules WHERE user_id = ?", (uid,))
    for c in courses:
        conn.execute(
            "INSERT INTO schedules (user_id, course_name, teacher, week_info, weekday, section, classroom) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uid, c["course_name"], c["teacher"], c["week_info"], c["weekday"], c["section"], c["classroom"]),
        )
    conn.commit()
    conn.close()


def save_exams(user_id: str, exams: list[dict[str, Any]]) -> None:
    conn = db_connect()
    uid = resolve_user_pk(conn, user_id)
    conn.execute("DELETE FROM exams WHERE user_id = ?", (uid,))
    for e in exams:
        conn.execute(
            "INSERT INTO exams (user_id, course_name, exam_time, exam_location, seat_number) "
            "VALUES (?, ?, ?, ?, ?)",
            (uid, e["course_name"], e["exam_time"], e["exam_location"], e["seat_number"]),
        )
    conn.commit()
    conn.close()


def schedule_state_path(user_id: str) -> Path:
    path = user_runtime_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    return path / "schedule_state.json"


def parse_current_week(html: str) -> int | None:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    patterns = [
        r"教学\s*第\s*(\d{1,2})\s*周",
        r"当前\s*教学\s*周\s*[:：]?\s*(\d{1,2})",
        r"当前周\s*[:：]?\s*(\d{1,2})",
        r"第\s*(\d{1,2})\s*周",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            week = int(match.group(1))
            if 1 <= week <= 30:
                return week
    return None


def read_current_week_from_browser(driver: Any, timeout: int = 12) -> int | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        week = parse_current_week(driver.page_source)
        if week:
            return week
        time.sleep(1)
    return parse_current_week(driver.page_source)


def save_current_week(user_id: str, current_week: int | None) -> None:
    if not current_week:
        return
    payload = {
        "current_week": current_week,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "source": "jwc_home",
    }
    schedule_state_path(user_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def first_monday(year: int, month: int) -> date:
    day = date(year, month, 1)
    offset = (7 - day.weekday()) % 7
    return date(year, month, 1 + offset)


def infer_current_week_from_term(term_id: str | None, today: date | None = None) -> int | None:
    if not term_id:
        return None
    match = re.match(r"(\d{4})-(\d{4})-(\d)", term_id)
    if not match:
        return None
    start_year = int(match.group(1))
    end_year = int(match.group(2))
    term_no = match.group(3)
    term_start = first_monday(start_year, 9) if term_no == "1" else first_monday(end_year, 3)
    current_date = today or date.today()
    delta = (current_date - term_start).days
    if delta < 0:
        return None
    week = delta // 7 + 1
    if 1 <= week <= 30:
        return week
    return None


def load_cached_current_week(user_id: str) -> int | None:
    path = schedule_state_path(user_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        week = int(data.get("current_week") or 0)
        if 1 <= week <= 30:
            return week
    except Exception:
        return None
    return None


def get_current_week(user_id: str | None = None) -> int:
    if user_id:
        cached_week = load_cached_current_week(user_id)
        if cached_week:
            return cached_week
    start_str = os.environ.get("SEMESTER_START_DATE", "")
    if not start_str:
        return -1
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
        today = date.today()
        delta = (today - start).days
        if delta < 0:
            return 0
        return delta // 7 + 1
    except ValueError:
        return -1


def week_matches(week_info: str, current_week: int) -> bool:
    if current_week <= 0 or not week_info:
        return True
    if re.search(r"单周|单$", week_info) and current_week % 2 == 0:
        return False
    if re.search(r"双周|双$", week_info) and current_week % 2 == 1:
        return False
    ranges = re.findall(r"(\d+)-(\d+)|(\d+)", week_info)
    if not ranges:
        return True
    for r_start, r_end, single in ranges:
        if single and current_week == int(single):
            return True
        if r_start and r_end and int(r_start) <= current_week <= int(r_end):
            return True
    return False


def build_week_schedule(user_id: str, target_week: int) -> dict[str, Any]:
    conn = db_connect()
    schedule_rows = conn.execute(
        "SELECT course_name, teacher, week_info, weekday, section, classroom FROM schedules "
        "WHERE user_id = ? ORDER BY weekday ASC, section ASC, id ASC",
        (user_id,),
    ).fetchall()
    conn.close()

    weekdays = [
        {"weekday": day, "weekday_name": f"周{label}", "courses": []}
        for day, label in enumerate(["一", "二", "三", "四", "五", "六", "日"], start=1)
    ]

    for row in schedule_rows:
        if not week_matches(row["week_info"], target_week):
            continue
        weekday = row["weekday"]
        if not weekday or weekday < 1 or weekday > 7:
            continue
        weekdays[weekday - 1]["courses"].append({
            "course_name": row["course_name"],
            "teacher": row["teacher"],
            "section": row["section"],
            "classroom": row["classroom"],
            "week_info": row["week_info"],
            "weekday": weekday,
        })

    return {"target_week": target_week, "weekdays": weekdays}


def cmd_list_week(user_id: str, offset_weeks: int = 0) -> None:
    current_week = get_current_week(user_id)
    if current_week <= 0:
        emit(True, "当前教学周未知", {
            "current_week": None,
            "target_week": None,
            "offset_weeks": offset_weeks,
            "weekdays": [],
        })

    target_week = current_week + offset_weeks
    if target_week < 1:
        target_week = 1

    data = build_week_schedule(user_id, target_week)
    data["current_week"] = current_week
    data["offset_weeks"] = offset_weeks
    emit(True, "执行成功", data)


def cmd_list_today(user_id: str) -> None:
    conn = db_connect()
    today = date.today()
    weekday = today.weekday() + 1
    today_str = today.isoformat()
    current_week = get_current_week(user_id)

    schedule_rows = conn.execute(
        "SELECT course_name, teacher, week_info, section, classroom FROM schedules "
        "WHERE user_id = ? AND weekday = ?",
        (user_id, weekday),
    ).fetchall()

    courses = []
    for row in schedule_rows:
        if week_matches(row["week_info"], current_week):
            courses.append({
                "course_name": row["course_name"],
                "teacher": row["teacher"],
                "section": row["section"],
                "classroom": row["classroom"],
                "week_info": row["week_info"],
            })

    task_rows = conn.execute(
        "SELECT id, title, category, priority, deadline, note, status FROM tasks "
        "WHERE user_id = ? AND status = 'pending' AND DATE(deadline) <= ? ORDER BY deadline ASC",
        (user_id, today_str),
    ).fetchall()

    month_prefix = today.strftime("%Y-%m")
    exam_rows = conn.execute(
        "SELECT id, course_name, exam_time, exam_location, seat_number FROM exams "
        "WHERE user_id = ? AND exam_time LIKE ? ORDER BY exam_time ASC, id ASC",
        (user_id, f"%{month_prefix}%"),
    ).fetchall()

    conn.close()
    emit(True, "执行成功", {
        "date": today_str,
        "weekday": weekday,
        "current_week": current_week if current_week > 0 else None,
        "courses": courses,
        "schedules": courses,
        "exams": [dict(r) for r in exam_rows],
        "tasks": [dict(r) for r in task_rows],
    })


def write_change_log(user_id: str, change_type: str, old_val: str, new_val: str, message: str) -> None:
    conn = db_connect()
    conn.execute(
        "INSERT INTO change_logs (user_id, change_type, old_value, new_value, message) VALUES (?, ?, ?, ?, ?)",
        (user_id, change_type, old_val, new_val, message),
    )
    conn.commit()
    conn.close()


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
            if "=" in name_value:
                name, value = name_value.split("=", 1)
                pairs.append((name, value, domain))
        elif "=" in line:
            name, value = line.split("=", 1)
            pairs.append((name, value, ".njfu.edu.cn"))
    return pairs


def _inject_cookies_into_browser(driver: Any, user_id: str, timeout: int) -> None:
    """Inject fresh cookies from webvpn.cookie file into the browser session.
    
    This ensures that even if the chrome profile has an expired session,
    the latest tokens from the cookie file take precedence.
    """
    try:
        from selenium.common.exceptions import TimeoutException
    except ImportError:
        return

    cookie_pairs = load_cookie_pairs(user_id)
    if not cookie_pairs:
        return

    print(json.dumps({"status": "injecting_fresh_cookies", "count": len(cookie_pairs)}, ensure_ascii=False), file=sys.stderr, flush=True)
    
    driver.get("https://webvpn.njfu.edu.cn")
    try:
        driver.execute_script("return document.readyState")
    except TimeoutException:
        pass

    for name, value, domain in cookie_pairs:
        cookie_dict = {
            "name": name,
            "value": value,
            "domain": domain.strip(),
            "path": "/",
            "secure": True,
            "httpOnly": False,
        }
        try:
            driver.add_cookie(cookie_dict)
        except Exception as e:
            print(json.dumps({"status": "cookie_inject_warning", "cookie": name, "error": str(e)}, ensure_ascii=False), file=sys.stderr, flush=True)


def fetch_schedule_html_with_browser(user_id: str) -> str:
    try:
        from selenium import webdriver
        from selenium.common.exceptions import TimeoutException, WebDriverException
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError as exc:
        raise RuntimeError("selenium is required for schedule sync; run: pip install selenium") from exc

    timeout = int(os.environ.get("SCHEDULE_BROWSER_TIMEOUT", "60"))
    profile_path = chrome_profile_path(user_id)
    if not profile_path.exists():
        raise RuntimeError("chrome profile not found; run bind_webvpn_interactive.sh first")

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
        # Move window off-screen so it's invisible to the user
        options.add_argument("--window-position=-2400,-2400")
        options.add_argument("--window-size=1280,800")

    print(json.dumps({"status": "starting_browser"}, ensure_ascii=False), file=sys.stderr, flush=True)
    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as exc:
        raise RuntimeError(f"failed to start Chrome/ChromeDriver: {exc}") from exc

    try:
        driver.set_page_load_timeout(timeout)
        print(json.dumps({"status": "using_auth_chrome_profile", "profile": str(profile_path)}, ensure_ascii=False), file=sys.stderr, flush=True)

        # Inject latest cookies from webvpn.cookie file into the browser so that
        # even if the chrome profile has an expired session, the fresh token wins.
        _inject_cookies_into_browser(driver, user_id, timeout)

        print(json.dumps({"status": "warming_jwc", "url": JWC_MAIN}, ensure_ascii=False), file=sys.stderr, flush=True)
        try:
            driver.get(JWC_MAIN)
        except TimeoutException:
            print(json.dumps({"status": "jwc_load_timeout", "current_url": driver.current_url}, ensure_ascii=False), file=sys.stderr, flush=True)

        try:
            WebDriverWait(driver, timeout * 2).until(
                lambda d: (
                    ("jsxsd" in d.current_url or "htmlx" in d.current_url)
                    and "authserver/login" not in d.current_url
                    and "rump_frontend/login" not in d.current_url
                )
            )
        except TimeoutException:
            print(json.dumps({"status": "jwc_warmup_timeout", "current_url": driver.current_url}, ensure_ascii=False), file=sys.stderr, flush=True)

        current = driver.current_url
        print(json.dumps({"status": "jwc_warmup_done", "current_url": current}, ensure_ascii=False), file=sys.stderr, flush=True)
        save_current_week(user_id, read_current_week_from_browser(driver, timeout=12))

        if "authserver/login" in current:
            if "casLoginForm" in driver.page_source:
                raise RuntimeError("webvpn auth expired (CAS login form appeared); run bind_webvpn_interactive.sh again")
            else:
                print(json.dumps({"status": "stuck_at_cas_but_no_form", "waiting": "5s"}, ensure_ascii=False), file=sys.stderr, flush=True)
                time.sleep(5)
                driver.get(JWC_MAIN)
                try:
                    WebDriverWait(driver, timeout).until(
                        lambda d: ("jsxsd" in d.current_url or "htmlx" in d.current_url)
                    )
                except TimeoutException:
                    if "casLoginForm" in driver.page_source:
                        raise RuntimeError("webvpn auth expired after retry")
                print(json.dumps({"status": "jwc_retry_succeeded", "current_url": driver.current_url}, ensure_ascii=False), file=sys.stderr, flush=True)

        if "rump_frontend/login" in driver.current_url:
            print(json.dumps({"status": "jwc_still_at_webvpn_router", "current_url": driver.current_url}, ensure_ascii=False), file=sys.stderr, flush=True)
            time.sleep(2)
            try:
                driver.get(JWC_MAIN)
            except TimeoutException:
                print(json.dumps({"status": "jwc_retry_timeout", "current_url": driver.current_url}, ensure_ascii=False), file=sys.stderr, flush=True)

        if "frontend_static/frontend/login/index.html" in driver.current_url:
            print(json.dumps({"status": "webvpn_portal_loaded_retrying_jwc"}, ensure_ascii=False), file=sys.stderr, flush=True)
            try:
                driver.get(JWC_MAIN)
            except TimeoutException:
                print(json.dumps({"status": "jwc_retry_timeout", "current_url": driver.current_url}, ensure_ascii=False), file=sys.stderr, flush=True)

        print(json.dumps({"status": "loading_schedule", "url": SCHEDULE_LIST_URL, "current_url": driver.current_url}, ensure_ascii=False), file=sys.stderr, flush=True)
        try:
            driver.get(SCHEDULE_LIST_URL)
        except TimeoutException:
            print(json.dumps({"status": "page_load_timeout", "current_url": driver.current_url}, ensure_ascii=False), file=sys.stderr, flush=True)

        try:
            WebDriverWait(driver, timeout).until(
                lambda d: "timetable" in d.page_source
                or "xskb_print.do" in d.page_source
                or "authserver/login" in d.current_url
            )
        except TimeoutException:
            pass

        if "authserver/login" in driver.current_url:
            raise RuntimeError("schedule page redirected to CAS login; run bind_webvpn_interactive.sh again; current_url=" + driver.current_url)

        if "rump_frontend/login" in driver.current_url:
            print(json.dumps({"status": "schedule_still_at_webvpn_router_retrying", "current_url": driver.current_url}, ensure_ascii=False), file=sys.stderr, flush=True)
            try:
                driver.get(SCHEDULE_LIST_URL)
            except TimeoutException:
                print(json.dumps({"status": "schedule_retry_timeout", "current_url": driver.current_url}, ensure_ascii=False), file=sys.stderr, flush=True)
            try:
                WebDriverWait(driver, timeout).until(
                    lambda d: "timetable" in d.page_source
                    or "xskb_print.do" in d.page_source
                    or "authserver/login" in d.current_url
                )
            except TimeoutException:
                pass
            if "authserver/login" in driver.current_url:
                raise RuntimeError("schedule page redirected to CAS login; run bind_webvpn_interactive.sh again; current_url=" + driver.current_url)

        html = driver.page_source
        save_current_week(user_id, infer_current_week_from_term(extract_schedule_params(html).get("xnxq01id")))
        if "timetable" not in html and "xskb_print.do" not in html:
            raise RuntimeError(
                "schedule page did not load timetable; current_url="
                + driver.current_url
                + "; html_length="
                + str(len(html))
            )
        return html
    finally:
        driver.quit()


def cmd_detect_changes(user_id: str) -> None:
    conn = db_connect()
    old_rows = conn.execute(
        "SELECT course_name, weekday, section, classroom FROM schedules WHERE user_id = ?", (user_id,)
    ).fetchall()
    conn.close()
    old_set = {(r["course_name"], r["weekday"], r["section"], r["classroom"]) for r in old_rows}

    html = fetch_schedule_html_with_browser(user_id)
    new_courses = parse_schedule(html)
    new_set = {(c["course_name"], c["weekday"], c["section"], c["classroom"]) for c in new_courses}

    changes = []
    for item in new_set - old_set:
        write_change_log(user_id, "schedule_added", "", str(item),
                         f"新增课程: {item[0]} 周{item[1]} 第{item[2]}节 {item[3]}")
        changes.append({"type": "added", "course": item[0], "weekday": item[1], "section": item[2]})

    for item in old_set - new_set:
        write_change_log(user_id, "schedule_removed", str(item), "",
                         f"移除课程: {item[0]} 周{item[1]} 第{item[2]}节 {item[3]}")
        changes.append({"type": "removed", "course": item[0], "weekday": item[1], "section": item[2]})

    save_schedules(user_id, new_courses)
    emit(True, f"detected {len(changes)} changes", {
        "added": len(new_set - old_set),
        "removed": len(old_set - new_set),
        "changes": changes,
    })


def cmd_sync_schedule(user_id: str) -> None:
    # Try requests first (faster, no browser popup)
    try:
        session = load_session(user_id)
        html, params = fetch_schedule_html(session)
        save_current_week(user_id, infer_current_week_from_term(params.get("xnxq01id")))
        
        # If timetable found in HTML, use it
        if "timetable" in html or "kbcontent" in html:
            courses = parse_schedule(html)
            if courses:
                save_schedules(user_id, courses)
                current_week = load_cached_current_week(user_id)
                emit(True, f"synced {len(courses)} courses", {"count": len(courses), "source": "requests", "current_week": current_week})
            # If parse failed but HTML looks valid, fall back to browser
        
        # If timetable not found, fall back to browser
        print(json.dumps({"status": "requests_no_timetable_fallback_to_browser"}, ensure_ascii=False), file=sys.stderr)
    except Exception as e:
        print(json.dumps({"status": "requests_failed", "error": str(e), "fallback_to_browser": True}, ensure_ascii=False), file=sys.stderr)
    
    # Fallback: use browser (slower but more reliable)
    html = fetch_schedule_html_with_browser(user_id)
    courses = parse_schedule(html)
    save_schedules(user_id, courses)
    current_week = load_cached_current_week(user_id)
    emit(True, f"synced {len(courses)} courses", {"count": len(courses), "source": "selenium", "current_week": current_week})


def cmd_sync_exam(user_id: str) -> None:
    session = load_session(user_id)
    html = fetch_exam_html(session)
    exams = parse_exams(html)
    save_exams(user_id, exams)
    emit(True, f"synced {len(exams)} exams", {"count": len(exams)})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["sync_schedule", "sync_exam", "list_today", "list_next_week", "detect_changes"])
    parser.add_argument("user_id")
    args = parser.parse_args()

    try:
        if args.action == "sync_schedule":
            cmd_sync_schedule(args.user_id)
        elif args.action == "sync_exam":
            cmd_sync_exam(args.user_id)
        elif args.action == "list_today":
            cmd_list_today(args.user_id)
        elif args.action == "list_next_week":
            cmd_list_week(args.user_id, 1)
        else:
            cmd_detect_changes(args.user_id)
    except Exception as exc:
        emit(False, str(exc), None)


if __name__ == "__main__":
    main()
