PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS notification_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    enable_email INTEGER DEFAULT 0,
    enable_desktop INTEGER DEFAULT 1,
    enable_seat_result INTEGER DEFAULT 1,
    enable_schedule_reminder INTEGER DEFAULT 1,
    enable_error_alert INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
