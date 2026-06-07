#!/usr/bin/env python3
"""Library seat reservation client for CampusPilot."""
from __future__ import annotations
import argparse, json, os, sqlite3, sys, time
from datetime import datetime
from pathlib import Path
from typing import Any
import requests, urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LIBRARY_BASE = (
    "https://webvpn.njfu.edu.cn/webvpn/LjIwMS4xNjkuMjE4LjE2OC4xNjc="
    "/LjIwNS4xNTguMjAwLjE3MS4xNTMuMTUwLjIxNi45Ny4yMTEuMTU2LjE1OC4xNzMuMTQ4LjE1NS4xNTUuMjE3LjEwMC4xNTAuMTY1"
)
LIBRARY_SSO_URL = "https://webvpn.njfu.edu.cn/rump_frontend/connect/?target=Library&id=12"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
TOKEN_TTL_SECONDS = 6 * 3600
CHROME_BINARY = os.environ.get("CHROME_BINARY") or str(Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe")
CHROMEDRIVER_PATH = os.environ.get("CHROMEDRIVER_PATH") or str(Path.home() / ".cache/selenium/chromedriver/win64/148.0.7778.178/chromedriver.exe")

# Room IDs by floor label (from library system HAR analysis)
FLOOR_ROOM_IDS: dict[str, list[int]] = {
    "2F": [100455344, 100455346],
    "3F": [100455350, 100455352, 100455354, 111488386],
    "4F": [100455356, 111488388],
    "5F": [100455358],
    "6F": [100455360],
    "7F": [106658017, 111488396],
}
ALL_ROOM_IDS = [rid for ids in FLOOR_ROOM_IDS.values() for rid in ids]


def emit(success: bool, message: str, data: Any = None, code: int | None = None) -> None:
    print(json.dumps({"success": success, "message": message, "data": data}, ensure_ascii=False))
    if code is not None:
        raise SystemExit(code)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def database_path() -> Path:
    return Path(os.environ.get("DATABASE_PATH", project_root() / "database" / "campuspilot.db"))


def user_runtime_dir(user_id: str) -> Path:
    base = os.environ.get("USERS_RUNTIME_DIR", str(project_root() / "runtime" / "users"))
    path = Path(base) / user_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def cookie_path(user_id: str) -> Path:
    return user_runtime_dir(user_id) / "webvpn.cookie"


def chrome_profile_path(user_id: str) -> Path:
    return user_runtime_dir(user_id) / "chrome_profile"


def library_token_path(user_id: str) -> Path:
    return user_runtime_dir(user_id) / "library_token.json"


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def load_webvpn_cookie_pairs(user_id: str) -> list[tuple[str, str, str]]:
    path = cookie_path(user_id)
    if not path.is_file():
        raise RuntimeError("webvpn cookie not found; please login via bind_webvpn_interactive.sh first")
    pairs: list[tuple[str, str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            parts = line.split("|")
            name_value, domain = parts[0], parts[1] if len(parts) > 1 else "webvpn.njfu.edu.cn"
            if "=" in name_value:
                name, value = name_value.split("=", 1)
                pairs.append((name, value, domain))
        elif "=" in line:
            name, value = line.split("=", 1)
            pairs.append((name, value, "webvpn.njfu.edu.cn"))
    return pairs


def save_seat_result(user_id: str, seat_no: str, reserve_time: str, status: str, reason: str) -> None:
    conn = db_connect()
    conn.execute(
        "INSERT INTO seat_results (user_id, seat_no, reserve_time, status, reason) VALUES (?, ?, ?, ?, ?)",
        (user_id, seat_no, reserve_time, status, reason),
    )
    conn.commit()
    conn.close()


def log_message(user_id: str, level: str, message: str, detail: str = "") -> None:
    conn = db_connect()
    conn.execute(
        "INSERT INTO logs (user_id, module, level, message, detail) VALUES (?, 'seat', ?, ?, ?)",
        (user_id, level, message, detail),
    )
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# Library token management
# ---------------------------------------------------------------------------

def _load_cached_token(user_id: str) -> dict[str, Any] | None:
    path = library_token_path(user_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - data.get("cached_at", 0) < TOKEN_TTL_SECONDS:
            return data
    except Exception:
        pass
    return None


def _save_token_cache(user_id: str, token: str, app_acc_no: int) -> None:
    path = library_token_path(user_id)
    path.write_text(json.dumps({"token": token, "app_acc_no": app_acc_no, "cached_at": time.time()}), encoding="utf-8")


def _delete_token_cache(user_id: str) -> None:
    try:
        library_token_path(user_id).unlink()
    except FileNotFoundError:
        pass


def _extract_auth_payload(data: dict[str, Any]) -> tuple[str, int | None]:
    payload = data.get("data") if isinstance(data.get("data"), dict) else data
    if not isinstance(payload, dict):
        return "", None
    token = payload.get("token") or payload.get("accessToken") or data.get("token") or ""
    acc_no = payload.get("accNo") or payload.get("appAccNo") or data.get("accNo") or data.get("appAccNo")
    return str(token or ""), int(acc_no) if acc_no else None


def _validate_library_token(token: str, user_id: str | None = None) -> tuple[bool, int | None]:
    if not token:
        return False, None
    session = make_library_session(token, user_id)
    for path in ("/ic-web/auth/userInfo", "/ic-web/auth/user"):
        try:
            url = f"{LIBRARY_BASE}{path}?vpn-12-libseat.njfu.edu.cn"
            resp = session.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()
            _, acc_no = _extract_auth_payload(data)
            if acc_no:
                return True, int(acc_no)
            if data.get("code") == 0:
                return True, None
        except Exception:
            continue
    return False, None


def get_library_token(user_id: str) -> tuple[str, int]:
    """Get library token and appAccNo, using cache or Selenium if needed."""
    cached = _load_cached_token(user_id)
    if cached:
        token = cached.get("token", "")
        app_acc_no = int(cached.get("app_acc_no") or 0)
        if token and app_acc_no:
            return token, app_acc_no
    token, app_acc_no = _fetch_token_via_browser(user_id)
    _save_token_cache(user_id, token, app_acc_no)
    return token, app_acc_no

def _find_first(driver: Any, selectors: list[tuple[str, str]]) -> Any | None:
    from selenium.webdriver.common.by import By
    by_map = {"css": By.CSS_SELECTOR, "xpath": By.XPATH, "id": By.ID}
    for kind, value in selectors:
        try:
            items = driver.find_elements(by_map[kind], value)
            if items:
                return items[0]
        except Exception:
            pass
    return None


def _click_library_redirect_and_seat_entry(driver: Any) -> None:
    if "rump_frontend" in driver.current_url:
        link = _find_first(driver, [("id", "url"), ("css", "a#url")])
        if link:
            link.click()
            time.sleep(2)
    before = set(driver.window_handles)
    entry = _find_first(driver, [
        ("xpath", "//a[contains(., '座位/空间预约')]"),
        ("xpath", "//a[contains(., '座位管理系统')]"),
        ("xpath", "//a[contains(., '座位预约') or contains(., '空间预约')]"),
        ("xpath", "//a[contains(@href, 'zwglxt') or contains(@href, 'seat') or contains(@href, 'reserve')]"),
        ("css", ".group-item-img-2"),
        ("xpath", "//*[contains(text(), '座位/空间预约')]"),
        ("xpath", "//*[contains(text(), '座位预约')]"),
        ("xpath", "//*[contains(text(), '空间预约')]"),
    ])
    if entry:
        href = ""
        try:
            href = entry.get_attribute("href") or ""
        except Exception:
            href = ""
        if href:
            driver.get(href)
        else:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", entry)
            except Exception:
                entry.click()
        time.sleep(2)
        new_handles = list(set(driver.window_handles) - before)
        if new_handles:
            driver.switch_to.window(new_handles[-1])
        elif driver.window_handles:
            driver.switch_to.window(driver.window_handles[-1])
        time.sleep(3)


def _storage_snapshot(driver: Any) -> dict[str, Any]:
    try:
        return driver.execute_script(
            """
            const dump = (storage) => {
              const data = {};
              for (let i = 0; i < storage.length; i++) {
                const key = storage.key(i);
                data[key] = storage.getItem(key);
              }
              return data;
            };
            return {localStorage: dump(window.localStorage), sessionStorage: dump(window.sessionStorage)};
            """
        ) or {}
    except Exception:
        return {}


def _find_auth_in_storage(snapshot: dict[str, Any]) -> tuple[str, int | None]:
    token = ""
    acc_no = None
    for bucket_name in ("localStorage", "sessionStorage"):
        bucket = snapshot.get(bucket_name) or {}
        if not isinstance(bucket, dict):
            continue
        for key, value in bucket.items():
            key_l = str(key).lower()
            if isinstance(value, str) and value:
                if ("token" in key_l or "authorization" in key_l) and len(value) >= 16:
                    token = token or value
                if value.startswith("{"):
                    try:
                        nested_token, nested_acc_no = _extract_auth_payload(json.loads(value))
                    except Exception:
                        continue
                    token = token or nested_token
                    acc_no = acc_no or nested_acc_no
    return token, acc_no


def _extract_library_auth_from_browser(driver: Any, timeout: int) -> tuple[str, int]:
    deadline = time.time() + timeout
    token = ""
    app_acc_no = 0
    user_info_paths = ["/ic-web/auth/userInfo", "/ic-web/auth/user"]
    while time.time() < deadline:
        try:
            token, app_acc_no = _find_auth_in_storage(_storage_snapshot(driver))
            if token and app_acc_no:
                return token, int(app_acc_no)
        except Exception:
            token = ""
            app_acc_no = 0
        for path in user_info_paths:
            url = f"{LIBRARY_BASE}{path}?vpn-12-libseat.njfu.edu.cn"
            try:
                raw = driver.execute_async_script(
                    """
                    var done = arguments[0];
                    var url = arguments[1];
                    var token = arguments[2] || '';
                    var controller = new AbortController();
                    var timer = setTimeout(function() { controller.abort(); done(null); }, 8000);
                    fetch(url, {headers: {token: token, Accept: 'application/json'}, signal: controller.signal})
                      .then(function(r) { return r.json(); })
                      .then(function(d) { clearTimeout(timer); done(JSON.stringify(d)); })
                      .catch(function() { clearTimeout(timer); done(null); });
                    """,
                    url,
                    token,
                )
            except Exception as exc:
                print(json.dumps({"status": "library_user_info_fetch_warning", "path": path, "error": str(exc)}, ensure_ascii=False), file=sys.stderr, flush=True)
                continue
            if not raw:
                continue
            data = json.loads(raw)
            response_token, acc_no = _extract_auth_payload(data)
            token = token or response_token
            if token and acc_no:
                app_acc_no = int(acc_no)
                return token, app_acc_no
        time.sleep(2)
    raise RuntimeError(f"library token/appAccNo not found; current_url={driver.current_url}")


def _fetch_token_via_browser(user_id: str) -> tuple[str, int]:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.common.exceptions import TimeoutException, WebDriverException
    except ImportError:
        raise RuntimeError("selenium required; run: pip install selenium")

    profile = chrome_profile_path(user_id)
    if not profile.exists():
        raise RuntimeError("chrome profile not found; run bind_webvpn_interactive.sh first")

    timeout = int(os.environ.get("LIBRARY_BROWSER_TIMEOUT", "60"))
    options = Options()
    options.page_load_strategy = "eager"
    options.add_argument(f"--user-data-dir={profile}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-position=-2400,-2400")
    options.add_argument("--window-size=1280,800")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    if CHROME_BINARY and Path(CHROME_BINARY).is_file():
        options.binary_location = CHROME_BINARY

    print(json.dumps({"status": "starting_browser_for_library_token", "chrome_binary": CHROME_BINARY, "chromedriver": CHROMEDRIVER_PATH}, ensure_ascii=False), file=sys.stderr, flush=True)

    try:
        service = Service(executable_path=CHROMEDRIVER_PATH) if CHROMEDRIVER_PATH and Path(CHROMEDRIVER_PATH).is_file() else Service()
        driver = webdriver.Chrome(service=service, options=options)
    except WebDriverException as exc:
        raise RuntimeError(f"failed to start Chrome/ChromeDriver: {exc}") from exc

    try:
        driver.set_page_load_timeout(timeout)
        driver.set_script_timeout(min(timeout, 15))
        driver.get("https://webvpn.njfu.edu.cn")
        for name, value, domain in load_webvpn_cookie_pairs(user_id):
            try:
                driver.add_cookie({"name": name, "value": value, "domain": domain.strip(), "path": "/", "secure": True})
            except Exception:
                pass

        print(json.dumps({"status": "navigating_to_library_sso", "url": LIBRARY_SSO_URL}, ensure_ascii=False), file=sys.stderr, flush=True)
        try:
            driver.get(LIBRARY_SSO_URL)
        except TimeoutException:
            pass

        time.sleep(2)
        _click_library_redirect_and_seat_entry(driver)
        token, app_acc_no = _extract_library_auth_from_browser(driver, timeout)
        print(json.dumps({"status": "library_token_acquired", "app_acc_no": app_acc_no}, ensure_ascii=False), file=sys.stderr, flush=True)
        return token, app_acc_no
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def _get_app_acc_no_from_browser(driver: Any, token: str, timeout: int) -> int:
    for path in ("/ic-web/auth/userInfo", "/ic-web/auth/user"):
        user_info_url = f"{LIBRARY_BASE}{path}?vpn-12-libseat.njfu.edu.cn"
        try:
            raw = driver.execute_async_script(
                """
                var done = arguments[0];
                var url = arguments[1];
                var token = arguments[2] || '';
                fetch(url, {headers: {token: token, Accept: 'application/json'}})
                  .then(function(r) { return r.json(); })
                  .then(function(d) { done(JSON.stringify(d)); })
                  .catch(function() { done(null); });
                """,
                user_info_url,
                token,
            )
            if raw:
                data = json.loads(raw)
                _, acc_no = _extract_auth_payload(data)
                if acc_no:
                    return int(acc_no)
        except Exception as exc:
            print(json.dumps({"status": "app_acc_no_fetch_warning", "path": path, "error": str(exc)}, ensure_ascii=False), file=sys.stderr, flush=True)
    raise RuntimeError("could not obtain appAccNo from library user info endpoints")


def make_library_session(token: str, user_id: str | None = None) -> requests.Session:
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "token": token,
        "Content-Type": "application/json;charset=UTF-8",
    })
    if user_id:
        for name, value, domain in load_webvpn_cookie_pairs(user_id):
            session.cookies.set(name, value, domain=domain.strip() or "webvpn.njfu.edu.cn", path="/")
    return session

def _room_ids_for_floor(floor: str) -> list[int]:
    if floor and floor.upper() in FLOOR_ROOM_IDS:
        return FLOOR_ROOM_IDS[floor.upper()]
    for key, ids in FLOOR_ROOM_IDS.items():
        if floor and key.startswith(floor.upper()):
            return ids
    return ALL_ROOM_IDS


def _seat_name_matches(api_name: str, floor: str, seat_no: str) -> bool:
    if api_name == seat_no:
        return True
    normalized = seat_no.strip().upper()
    api_normalized = api_name.strip().upper()
    floor_normalized = (floor or "").strip().upper()
    if api_normalized.endswith("-" + normalized):
        return True
    if floor_normalized and api_normalized == f"{floor_normalized}-{normalized}":
        return True
    return False


def check_seat_status(session: requests.Session, floor: str, seat_no: str, reserve_date: str | None = None) -> dict[str, Any]:
    date_str = (reserve_date or datetime.now().strftime("%Y%m%d")).replace("-", "")
    room_ids = _room_ids_for_floor(floor)
    last_error = ""
    for room_id in room_ids:
        url = f"{LIBRARY_BASE}/ic-web/reserve?vpn-12-libseat.njfu.edu.cn&roomIds={room_id}&resvDates={date_str}&sysKind=8"
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        try:
            body = resp.json()
        except ValueError as exc:
            preview = resp.text[:120].replace("\n", " ")
            raise RuntimeError(f"library API returned non-JSON response; roomId={room_id}, preview={preview}") from exc
        if body.get("code") != 0:
            last_error = f"{body.get('message', 'unknown')}; roomId={room_id}, resvDates={date_str}"
            continue
        for seat in body.get("data", []):
            api_name = str(seat.get("devName") or "")
            if _seat_name_matches(api_name, floor, seat_no):
                dev_status = seat.get("devStatus", -1)
                status_map = {0: "free", 1: "occupied", 2: "temp_away"}
                return {
                    "available": dev_status == 0,
                    "status": status_map.get(dev_status, "unknown"),
                    "seat_no": seat_no,
                    "dev_name": api_name,
                    "room_id": room_id,
                    "dev_id": seat.get("devId"),
                }
    if last_error:
        raise RuntimeError(f"library API error: {last_error}; floor={floor}, roomIds={','.join(str(r) for r in room_ids)}")
    return {"available": False, "status": "not_found", "seat_no": seat_no, "dev_id": None}

def _get_dev_id(session: requests.Session, floor: str, seat_no: str, reserve_date: str) -> int:
    info = check_seat_status(session, floor, seat_no, reserve_date)
    dev_id = info.get("dev_id")
    if dev_id is None:
        raise RuntimeError(f"seat '{seat_no}' not found")
    return int(dev_id)


def reserve_seat(session: requests.Session, app_acc_no: int, seat_no: str, floor: str, reserve_date: str, start_time: str, end_time: str) -> dict[str, Any]:
    dev_id = _get_dev_id(session, floor, seat_no, reserve_date)
    url = f"{LIBRARY_BASE}/ic-web/reserve?vpn-12-libseat.njfu.edu.cn"
    begin_ms = int(datetime.strptime(f"{reserve_date} {start_time}", "%Y-%m-%d %H:%M").timestamp() * 1000)
    end_ms = int(datetime.strptime(f"{reserve_date} {end_time}", "%Y-%m-%d %H:%M").timestamp() * 1000)
    body = {
        "sysKind": 8, "appAccNo": app_acc_no, "memberKind": 1, "resvMember": [app_acc_no],
        "resvBeginTime": begin_ms, "resvEndTime": end_ms,
        "testName": "", "captcha": "", "resvProperty": 0, "resvDev": [dev_id], "memo": "",
    }
    resp = session.post(url, json=body, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") == 0:
        data = result.get("data") or {}
        return {"success": True, "message": result.get("message", "预约成功"), "uuid": data.get("uuid"), "resv_id": data.get("resvId")}
    return {"success": False, "message": result.get("message", "预约失败"), "uuid": None, "resv_id": None}


def _get_current_reservation_uuid(session: requests.Session, app_acc_no: int, seat_no: str) -> str | None:
    today = datetime.now().strftime("%Y%m%d")
    url = f"{LIBRARY_BASE}/ic-web/reserve/resvInfo?vpn-12-libseat.njfu.edu.cn&resvDates={today}&appAccNo={app_acc_no}&sysKind=8"
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") == 0:
            for item in body.get("data", []):
                if item.get("devName") == seat_no and item.get("uuid"):
                    return item["uuid"]
    except Exception:
        pass
    return None


def cancel_seat_reservation(session: requests.Session, app_acc_no: int, seat_no: str, uuid: str | None = None) -> dict[str, Any]:
    target_uuid = uuid or _get_current_reservation_uuid(session, app_acc_no, seat_no)
    if not target_uuid:
        return {"success": False, "message": f"no active reservation found for seat {seat_no}"}
    url = f"{LIBRARY_BASE}/ic-web/reserve/delete?vpn-12-libseat.njfu.edu.cn"
    resp = session.post(url, json={"uuid": target_uuid}, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") == 0:
        return {"success": True, "message": result.get("message", "取消成功")}
    return {"success": False, "message": result.get("message", "取消失败")}

def _get_time_slots(config: sqlite3.Row) -> list[dict[str, str]]:
    slots = json.loads(config["reserve_time_slots"] or "[]")
    if not slots and config["reserve_start_time"]:
        slots = [{"start_time": config["reserve_start_time"], "end_time": config["reserve_end_time"]}]
    return slots


def _is_within_check_window(config: sqlite3.Row) -> bool:
    now = datetime.now()
    if config["check_start_time"]:
        sh, sm = map(int, config["check_start_time"].split(":"))
        if (now.hour, now.minute) < (sh, sm):
            return False
    if config["check_stop_time"]:
        eh, em = map(int, config["check_stop_time"].split(":"))
        if (now.hour, now.minute) > (eh, em):
            return False
    return True

def cmd_check(user_id: str, floor: str, seat_no: str) -> None:
    token, app_acc_no = get_library_token(user_id)
    session = make_library_session(token, user_id)
    result = check_seat_status(session, floor, seat_no)
    emit(True, "Seat status checked", result, 0)

def cmd_reserve(user_id: str, seat_no: str, floor: str, reserve_date: str, start_time: str, end_time: str, time_slots_json: str) -> None:
    token, app_acc_no = get_library_token(user_id)
    session = make_library_session(token, user_id)
    try:
        time_slots = json.loads(time_slots_json) if time_slots_json else []
    except Exception:
        time_slots = []
    if not time_slots and start_time and end_time:
        time_slots = [{"start_time": start_time, "end_time": end_time}]
    if not time_slots:
        emit(False, "No time slots provided", None, 1)
    date = reserve_date or datetime.now().strftime("%Y-%m-%d")
    for slot in time_slots:
        try:
            result = reserve_seat(session, app_acc_no, seat_no, floor, date, slot["start_time"], slot["end_time"])
            if result.get("success"):
                reserve_time = f"{date} {slot['start_time']}-{slot['end_time']}"
                save_seat_result(user_id, seat_no, reserve_time, "success", result.get("message", ""))
                log_message(user_id, "INFO", f"Seat reserved: {seat_no}", reserve_time)
                emit(True, "Seat reserved successfully", result, 0)
        except Exception as exc:
            save_seat_result(user_id, seat_no, "", "error", str(exc))
            log_message(user_id, "ERROR", f"Reservation error: {seat_no}", str(exc))
    emit(False, "All time slots failed", None, 1)

def cmd_cancel(user_id: str, seat_no: str, uuid: str = "") -> None:
    token, app_acc_no = get_library_token(user_id)
    session = make_library_session(token, user_id)
    result = cancel_seat_reservation(session, app_acc_no, seat_no, uuid or None)
    if result.get("success"):
        log_message(user_id, "INFO", f"Reservation cancelled: {seat_no}")
        emit(True, "Reservation cancelled", result, 0)
    else:
        emit(False, result.get("message", "Failed to cancel"), None, 1)

def cmd_retry(user_id: str) -> None:
    conn = db_connect()
    configs = conn.execute(
        "SELECT * FROM seat_configs WHERE user_id = ? AND enabled IN (1, '1', 'true', 'TRUE') ORDER BY priority ASC", (user_id,)
    ).fetchall()
    conn.close()
    if not configs:
        emit(False, "No enabled seat configs found", None, 1)
    token, app_acc_no = get_library_token(user_id)
    session = make_library_session(token, user_id)
    for config in configs:
        date = config["reserve_date"] or datetime.now().strftime("%Y-%m-%d")
        floor = config["floor"] or ""
        for slot in _get_time_slots(config):
            try:
                result = reserve_seat(session, app_acc_no, config["seat_no"], floor, date, slot["start_time"], slot["end_time"])
                if result.get("success"):
                    reserve_time = f"{date} {slot['start_time']}-{slot['end_time']}"
                    save_seat_result(user_id, config["seat_no"], reserve_time, "success", result.get("message", ""))
                    log_message(user_id, "INFO", f"Retry succeeded: {config['seat_no']}", reserve_time)
                    emit(True, "Seat reserved successfully", result, 0)
            except Exception as exc:
                log_message(user_id, "ERROR", f"Retry error: {config['seat_no']}", str(exc))
    emit(False, "All retry attempts failed", None, 1)

def cmd_worker(user_id: str) -> None:
    log_message(user_id, "INFO", "Worker preparing library token", "")
    token, app_acc_no = get_library_token(user_id)
    session = make_library_session(token, user_id)
    log_message(user_id, "INFO", "Worker library token ready", f"app_acc_no={app_acc_no}")
    processed_configs: set[int] = set()

    while True:
        conn = db_connect()
        configs = conn.execute(
            "SELECT * FROM seat_configs WHERE user_id = ? AND enabled IN (1, '1', 'true', 'TRUE') ORDER BY priority ASC", (user_id,)
        ).fetchall()
        conn.close()

        if not configs:
            log_message(user_id, "INFO", "Worker waiting for enabled seat configs", "")
            time.sleep(10)
            continue

        did_work = False
        for config in configs:
            config_id = int(config["id"])
            if config_id in processed_configs:
                continue
            if not _is_within_check_window(config):
                continue

            did_work = True
            attempt_start = time.time()
            max_duration = (config["max_duration_minutes"] or 15) * 60
            retry_count, max_retries = 0, config["max_retry_count"]
            date = config["reserve_date"] or datetime.now().strftime("%Y-%m-%d")
            floor = config["floor"] or ""
            log_message(user_id, "INFO", f"Worker trying seat: {config['seat_no']}", f"floor={floor}, date={date}, retries={max_retries}")

            while retry_count < max_retries:
                if time.time() - attempt_start > max_duration:
                    log_message(user_id, "INFO", "Worker max duration reached", config["seat_no"])
                    return
                if not _is_within_check_window(config):
                    log_message(user_id, "INFO", "Worker check window ended", config["seat_no"])
                    processed_configs.add(config_id)
                    break
                try:
                    for slot in _get_time_slots(config):
                        result = reserve_seat(session, app_acc_no, config["seat_no"], floor, date, slot["start_time"], slot["end_time"])
                        if result.get("success"):
                            reserve_time = f"{date} {slot['start_time']}-{slot['end_time']}"
                            save_seat_result(user_id, config["seat_no"], reserve_time, "success", result.get("message", ""))
                            log_message(user_id, "INFO", f"Worker reserved seat: {config['seat_no']}", reserve_time)
                            return
                    retry_count += 1
                    if retry_count < max_retries:
                        time.sleep(config["retry_interval"] or 10)
                except Exception as exc:
                    log_message(user_id, "ERROR", f"Worker error: {config['seat_no']}", str(exc))
                    retry_count += 1
                    if retry_count < max_retries:
                        time.sleep(config["retry_interval"] or 10)

            if retry_count >= max_retries:
                processed_configs.add(config_id)
                save_seat_result(user_id, config["seat_no"], "", "failed", "Max retries exceeded")
                log_message(user_id, "WARNING", f"Worker gave up on seat: {config['seat_no']}", "max retries exceeded")

        if did_work and len(processed_configs) >= len(configs):
            log_message(user_id, "INFO", "Worker finished all enabled seat configs", "")
            return

        time.sleep(10)

def main() -> None:
    parser = argparse.ArgumentParser(description="CampusPilot library seat client")
    parser.add_argument("action", choices=["check", "reserve", "cancel", "retry", "worker"])
    parser.add_argument("user_id")
    parser.add_argument("args", nargs="*")
    a = parser.parse_args()
    try:
        if a.action == "check":
            floor = a.args[0] if a.args else ""
            seat_no = a.args[1] if len(a.args) > 1 else ""
            cmd_check(a.user_id, floor, seat_no)
        elif a.action == "reserve":
            seat_no = a.args[0] if a.args else ""
            floor = a.args[1] if len(a.args) > 1 else ""
            date = a.args[2] if len(a.args) > 2 else ""
            start = a.args[3] if len(a.args) > 3 else ""
            end = a.args[4] if len(a.args) > 4 else ""
            slots_json = a.args[5] if len(a.args) > 5 else "[]"
            cmd_reserve(a.user_id, seat_no, floor, date, start, end, slots_json)
        elif a.action == "cancel":
            seat_no = a.args[0] if a.args else ""
            uuid = a.args[1] if len(a.args) > 1 else ""
            cmd_cancel(a.user_id, seat_no, uuid)
        elif a.action == "retry":
            cmd_retry(a.user_id)
        else:
            cmd_worker(a.user_id)
    except Exception as exc:
        emit(False, str(exc), None, 1)


if __name__ == "__main__":
    main()
