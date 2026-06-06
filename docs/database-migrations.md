# CampusPilot 数据库迁移说明

本文档说明 SQLite 数据库结构升级顺序和注意事项。

## 1. 数据库文件

默认数据库：

```text
database/campuspilot.db
```

完整建表脚本：

```text
database/schema.sql
```

增量迁移目录：

```text
database/migrations/
```

## 2. 初始化新数据库

新环境可直接使用 `schema.sql` 初始化：

```powershell
sqlite3 database\campuspilot.db ".read database\schema.sql"
```

也可以由 Flask 启动时通过 `init_database()` 自动初始化。

## 3. 迁移顺序

已有数据库按文件编号顺序执行：

```text
001_init.sql
002_add_seat_tables.sql
003_add_notification.sql
004_add_feedback.sql
005_add_account_auth.sql
006_add_admin_settings.sql
007_add_seat_time_slots.sql
008_add_default_reminder_settings.sql
```

执行示例：

```powershell
sqlite3 database\campuspilot.db ".read database\migrations\007_add_seat_time_slots.sql"
sqlite3 database\campuspilot.db ".read database\migrations\008_add_default_reminder_settings.sql"
```

## 4. 重要注意事项

SQLite 的：

```sql
ALTER TABLE ... ADD COLUMN ...
```

重复执行会报错：

```text
duplicate column name
```

所以迁移文件不要重复执行。建议执行前先检查表结构：

```powershell
sqlite3 database\campuspilot.db "PRAGMA table_info(seat_configs);"
sqlite3 database\campuspilot.db "PRAGMA table_info(notification_settings);"
```

## 5. 关键迁移说明

### 005_add_account_auth.sql

新增多用户账号体系：

```text
users
user_sessions
campus_accounts
```

用途：

```text
系统账号注册/登录
Session token
校园网账号加密绑定
user/admin 角色
```

### 006_add_admin_settings.sql

新增管理员配置：

```text
admin_settings
```

用途：

```text
配置用户反馈接收邮箱
```

### 007_add_seat_time_slots.sql

为抢座配置增加多时间段字段：

```sql
ALTER TABLE seat_configs ADD COLUMN reserve_time_slots TEXT;
```

用途：

```text
保存多个预约时间段 JSON
```

示例：

```json
[
  {"start_time": "07:30", "end_time": "09:30"},
  {"start_time": "19:00", "end_time": "22:00"}
]
```

### 008_add_default_reminder_settings.sql

为通知设置增加默认提醒规则：

```sql
ALTER TABLE notification_settings ADD COLUMN schedule_default_reminders TEXT DEFAULT '[15]';
ALTER TABLE notification_settings ADD COLUMN exam_default_reminders TEXT DEFAULT '[1440, 120]';
ALTER TABLE notification_settings ADD COLUMN task_default_reminders TEXT DEFAULT '[1440, 120]';
```

单位：分钟。

默认含义：

```text
课程：提前 15 分钟
考试：提前 1 天 + 提前 2 小时
DDL：提前 1 天 + 提前 2 小时
```

## 6. 后台创建管理员

普通注册接口永远只创建 `user`。管理员账号通过后台脚本创建：

```powershell
python backend\scripts\create_admin.py --username admin --password Admin123456 --email admin@example.com
```

## 7. 迁移后的检查

执行迁移后建议运行：

```powershell
python -m pytest tests\backend
```

当前后端测试预期：

```text
30 passed
```

## 8. 数据库备份建议

执行迁移前建议备份：

```powershell
Copy-Item database\campuspilot.db database\campuspilot.backup.db
```

如果迁移失败，可恢复：

```powershell
Copy-Item database\campuspilot.backup.db database\campuspilot.db -Force
```

## 9. 关于 MySQL 迁移

当前项目使用 SQLite。后续如需迁移 MySQL，需要单独处理：

```text
SQLite 的 ? 占位符与 MySQL 的 %s 不同
AUTOINCREMENT 语法不同
时间函数不同
schema.sql 需要转换
```

建议课程项目阶段继续使用 SQLite，后续云端高并发版本再作为独立任务迁移 MySQL。
