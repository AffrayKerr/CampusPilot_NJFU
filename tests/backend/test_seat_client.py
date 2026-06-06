"""Unit tests for seat_client.py - library seat reservation logic."""
import json
import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

SHELL_DIR = Path(__file__).resolve().parents[2] / "shell"
if str(SHELL_DIR) not in sys.path:
    sys.path.insert(0, str(SHELL_DIR))

from seat import seat_client


@pytest.fixture
def temp_runtime(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime" / "users"
    runtime.mkdir(parents=True)
    monkeypatch.setenv("USERS_RUNTIME_DIR", str(runtime))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    return runtime


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db))
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE seat_configs (
            id INTEGER PRIMARY KEY, user_id INTEGER, floor TEXT, seat_no TEXT,
            priority INTEGER DEFAULT 1, reserve_date TEXT,
            reserve_start_time TEXT, reserve_end_time TEXT,
            reserve_time_slots TEXT, check_start_time TEXT, check_stop_time TEXT,
            retry_interval INTEGER DEFAULT 10, max_retry_count INTEGER DEFAULT 30,
            max_duration_minutes INTEGER DEFAULT 15, enabled INTEGER DEFAULT 1
        );
        CREATE TABLE seat_results (
            id INTEGER PRIMARY KEY, user_id INTEGER, seat_no TEXT,
            reserve_time TEXT, status TEXT, reason TEXT
        );
        CREATE TABLE logs (
            id INTEGER PRIMARY KEY, user_id INTEGER, module TEXT,
            level TEXT, message TEXT, detail TEXT
        );
    """)
    conn.commit()
    conn.close()
    return db


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------

class TestTokenCache:
    def test_returns_none_when_no_file(self, temp_runtime):
        assert seat_client._load_cached_token("u1") is None

    def test_returns_token_when_fresh(self, temp_runtime):
        d = temp_runtime / "u1"
        d.mkdir()
        (d / "library_token.json").write_text(json.dumps({
            "token": "tok123", "app_acc_no": 111, "cached_at": time.time()
        }))
        result = seat_client._load_cached_token("u1")
        assert result["token"] == "tok123"
        assert result["app_acc_no"] == 111

    def test_returns_none_when_expired(self, temp_runtime):
        d = temp_runtime / "u1"
        d.mkdir()
        (d / "library_token.json").write_text(json.dumps({
            "token": "old", "app_acc_no": 0, "cached_at": time.time() - 7 * 3600
        }))
        assert seat_client._load_cached_token("u1") is None

    def test_save_creates_file_with_correct_content(self, temp_runtime):
        seat_client._save_token_cache("u1", "newtoken", 999)
        path = temp_runtime / "u1" / "library_token.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["token"] == "newtoken"
        assert data["app_acc_no"] == 999
        assert "cached_at" in data

    def test_uses_cache_when_fresh(self, temp_runtime):
        d = temp_runtime / "u1"
        d.mkdir()
        (d / "library_token.json").write_text(json.dumps({
            "token": "cached_tok", "app_acc_no": 42, "cached_at": time.time()
        }))
        with patch.object(seat_client, "_fetch_token_via_browser") as mock_fetch:
            tok, acc = seat_client.get_library_token("u1")
        assert tok == "cached_tok"
        assert acc == 42
        mock_fetch.assert_not_called()

    def test_fetches_when_cache_missing(self, temp_runtime):
        with patch.object(seat_client, "_fetch_token_via_browser", return_value=("fresh", 77)):
            tok, acc = seat_client.get_library_token("u1")
        assert tok == "fresh"
        assert acc == 77


# ---------------------------------------------------------------------------
# Room ID mapping
# ---------------------------------------------------------------------------

class TestRoomMapping:
    def test_known_floor_exact(self):
        assert seat_client._room_ids_for_floor("4F") == [100500004, 100500005]

    def test_known_floor_lowercase(self):
        assert seat_client._room_ids_for_floor("4f") == [100500004, 100500005]

    def test_numeric_prefix(self):
        assert seat_client._room_ids_for_floor("4") == [100500004, 100500005]

    def test_unknown_floor_returns_all(self):
        assert seat_client._room_ids_for_floor("9F") == seat_client.ALL_ROOM_IDS

    def test_empty_string_returns_all(self):
        assert seat_client._room_ids_for_floor("") == seat_client.ALL_ROOM_IDS


# ---------------------------------------------------------------------------
# check_seat_status
# ---------------------------------------------------------------------------

class TestCheckSeatStatus:
    def _session(self, data):
        m = Mock()
        r = Mock()
        r.json.return_value = data
        m.get.return_value = r
        return m

    def test_free_seat(self):
        s = self._session({"code": 0, "data": [
            {"devName": "4F-A161", "devId": 100500005, "devStatus": 0}
        ]})
        result = seat_client.check_seat_status(s, "4F", "4F-A161")
        assert result["available"] is True
        assert result["status"] == "free"
        assert result["dev_id"] == 100500005

    def test_occupied_seat(self):
        s = self._session({"code": 0, "data": [
            {"devName": "4F-A161", "devId": 100500005, "devStatus": 1}
        ]})
        result = seat_client.check_seat_status(s, "4F", "4F-A161")
        assert result["available"] is False
        assert result["status"] == "occupied"

    def test_temp_away(self):
        s = self._session({"code": 0, "data": [
            {"devName": "4F-A161", "devId": 100500005, "devStatus": 2}
        ]})
        result = seat_client.check_seat_status(s, "4F", "4F-A161")
        assert result["available"] is False
        assert result["status"] == "temp_away"

    def test_seat_not_in_list(self):
        s = self._session({"code": 0, "data": []})
        result = seat_client.check_seat_status(s, "4F", "4F-NONE")
        assert result["available"] is False
        assert result["status"] == "not_found"
        assert result["dev_id"] is None

    def test_api_error_raises(self):
        s = self._session({"code": -1, "message": "服务器错误"})
        with pytest.raises(RuntimeError, match="library API error"):
            seat_client.check_seat_status(s, "4F", "4F-A161")

    def test_date_strip_hyphens(self):
        s = self._session({"code": 0, "data": []})
        seat_client.check_seat_status(s, "4F", "4F-A161", "2026-06-08")
        url = s.get.call_args[0][0]
        assert "20260608" in url
