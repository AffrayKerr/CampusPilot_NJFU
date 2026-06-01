PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS seat_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    floor TEXT,
    seat_no TEXT NOT NULL,
    priority INTEGER DEFAULT 1,
    reserve_date TEXT,
    reserve_start_time TEXT,
    reserve_end_time TEXT,
    check_start_time TEXT,
    check_stop_time TEXT,
    retry_interval INTEGER DEFAULT 10,
    max_retry_count INTEGER DEFAULT 30,
    max_duration_minutes INTEGER DEFAULT 15,
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS seat_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    seat_no TEXT,
    reserve_time TEXT,
    status TEXT NOT NULL,
    reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
