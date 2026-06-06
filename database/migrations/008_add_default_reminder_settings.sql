ALTER TABLE notification_settings ADD COLUMN schedule_default_reminders TEXT DEFAULT '[15]';
ALTER TABLE notification_settings ADD COLUMN exam_default_reminders TEXT DEFAULT '[1440, 120]';
ALTER TABLE notification_settings ADD COLUMN task_default_reminders TEXT DEFAULT '[1440, 120]';
