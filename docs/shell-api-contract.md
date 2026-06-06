# CampusPilot Shell 对接协议

本文档面向成员 A，说明 Flask 调用 Shell 的脚本路径、参数顺序、用户隔离规则和返回格式。

## 1. 总体约定

Flask 调用 Shell 时会传入当前用户 `user_id`。所有 Shell 脚本必须按 `user_id` 读写数据，不能操作其他用户数据。

Shell 输出必须是 JSON：

```json
{
  "success": true,
  "message": "执行成功",
  "data": {}
}
```

失败示例：

```json
{
  "success": false,
  "message": "失败原因",
  "data": null
}
```

建议退出码：

```text
0     成功
非 0  失败
```

所有 SQL 必须带用户过滤，例如：

```sql
WHERE user_id = ?
```

## 2. 用户隔离文件约定

多用户场景下，Cookie、PID、Lock、日志文件必须按用户隔离。

推荐路径：

```text
runtime/users/{user_id}/webvpn.cookie
runtime/users/{user_id}/seat_worker.lock
runtime/users/{user_id}/seat_worker.pid
runtime/users/{user_id}/seat_worker.log
```

同一用户不能重复启动多个抢座 worker，不同用户可以同时运行。

## 3. WebVPN / 认证脚本

```text
shell/auth/login_bound.sh user_id
shell/auth/check_session.sh user_id
shell/auth/refresh_session.sh user_id
shell/auth/logout.sh user_id
```

说明：

- 校园网账号和加密密码存储在 `campus_accounts` 表。
- Shell 通过 `user_id` 查询当前用户绑定信息。
- Cookie 文件路径建议写回 `campus_accounts.webvpn_cookie_path` 或 `sessions.cookie_path`。

## 4. 课表与考试脚本

```text
shell/schedule/sync_schedule.sh user_id
shell/schedule/sync_exam.sh user_id
shell/schedule/list_today.sh user_id
shell/schedule/detect_changes.sh user_id
```

职责：

- `sync_schedule.sh`：抓取教务课表，写入 `schedules`。
- `sync_exam.sh`：抓取考试安排，写入 `exams`。
- `list_today.sh`：查询今日课程和待办。
- `detect_changes.sh`：重新抓取后与旧数据对比，写入 `change_logs`，必要时触发通知。

任务脚本：

```text
shell/schedule/add_task.sh user_id title deadline priority category repeat_rule reminder_time note
shell/schedule/update_task.sh user_id task_id title deadline priority category repeat_rule reminder_time note status
shell/schedule/delete_task.sh user_id task_id
```

`priority`：`high` / `medium` / `low`。

`status`：`pending` / `done` / `cancelled`。

## 5. 抢座脚本

### 5.1 候选座位配置

新增配置：

```text
shell/seat/seat_config.sh user_id floor seat_no priority reserve_date reserve_start_time reserve_end_time check_start_time check_stop_time retry_interval max_retry_count max_duration_minutes enabled reserve_time_slots_json
```

查看配置：

```text
shell/seat/list_configs.sh user_id
```

更新配置：

```text
shell/seat/update_config.sh user_id config_id floor seat_no priority reserve_date reserve_start_time reserve_end_time check_start_time check_stop_time retry_interval max_retry_count max_duration_minutes enabled reserve_time_slots_json
```

删除配置：

```text
shell/seat/delete_config.sh user_id config_id
```

`reserve_time_slots_json` 示例：

```json
[
  {"start_time": "07:30", "end_time": "09:30"},
  {"start_time": "19:00", "end_time": "22:00"}
]
```

Flask 已完成校验：

- 每段至少 2 小时。
- 周一到周四、周六、周日：`07:30-22:00`。
- 周五：`07:30-20:00`。

Shell 仍应信任但可二次校验。

### 5.2 座位检查与预约

```text
shell/seat/check_seat.sh user_id floor seat_no
shell/seat/reserve_seat.sh user_id seat_no reserve_date reserve_start_time reserve_end_time reserve_time_slots_json
shell/seat/cancel_seat.sh user_id seat_no
shell/seat/list_results.sh user_id limit
shell/seat/retry_seat.sh user_id
```

### 5.3 Worker 管理

```text
shell/seat/start_worker.sh user_id
shell/seat/seat_worker.sh user_id
shell/seat/stop_worker.sh user_id
shell/seat/worker_status.sh user_id
```

推荐逻辑：

1. `start_worker.sh` 检查 `runtime/users/{user_id}/seat_worker.lock`。
2. 未运行时后台启动 `seat_worker.sh user_id`。
3. 记录 PID 到 `runtime/users/{user_id}/seat_worker.pid`。
4. `seat_worker.sh` 只读取当前用户 `enabled=1` 的 `seat_configs`。
5. 按 `priority ASC, id ASC` 尝试候选座位。
6. 按 `reserve_time_slots_json` 尝试多个预约时间段。
7. 遇到网络波动、无座、登录超时按 `retry_interval` 重试。
8. 达到 `max_retry_count`、`max_duration_minutes` 或 `check_stop_time` 后停止。
9. 写入 `seat_results`、`logs`，并按通知设置触发通知。

推荐查询：

```sql
SELECT *
FROM seat_configs
WHERE user_id = ? AND enabled = 1
ORDER BY priority ASC, id ASC;
```

## 6. 通知脚本

```text
shell/notification/test_notify.sh user_id channel title content
shell/notification/notify_email.sh user_id subject content to
shell/notification/notify_desktop.sh user_id title content
shell/notification/notify_feedback.sh feedback_id
```

`channel`：`email` / `desktop` / `all`。

通知前建议读取 `notification_settings`：

- `enable_email`
- `enable_desktop`
- `enable_seat_result`
- `enable_schedule_reminder`
- `enable_error_alert`

## 7. 提醒 Worker 建议

提醒配置由 Flask API 管理：

- `notification_settings.schedule_default_reminders`
- `notification_settings.exam_default_reminders`
- `notification_settings.task_default_reminders`
- `reminders`

Shell 提醒 worker 可按以下逻辑：

1. 扫描 `reminders WHERE enabled = 1`。
2. 根据 `target_type` JOIN `schedules` / `exams` / `tasks`。
3. 计算 `target_time - remind_before_minutes`。
4. 到达提醒时间后发送邮件/桌面通知。
5. 通知内容应包含目标名称、时间、地点、备注 `note`。
6. 写入 `logs`。

## 8. 日志脚本

```text
shell/system/query_logs.sh user_id module level limit
```

普通用户只查询自己的日志。管理员全局日志由 Flask 管理员接口直接处理或调用专门管理脚本。

日志写入建议：

```sql
INSERT INTO logs (user_id, module, level, message, detail)
VALUES (?, ?, ?, ?, ?);
```

`module` 建议：

```text
auth
schedule
seat
notification
feedback
system
```

`level` 建议：

```text
DEBUG
INFO
WARNING
ERROR
CRITICAL
```

## 9. 用户配置导入导出

```text
shell/user/export_config.sh user_id export_path
shell/user/import_config.sh user_id import_path
```

导出建议包含：

- `notification_settings`
- `reminders`
- `seat_configs`
- `tasks`

不要导出：

- 明文校园网密码
- session token
- Cookie 文件

## 10. Shell 返回数据示例

抢座 worker 状态：

```json
{
  "success": true,
  "message": "Seat worker status",
  "data": {
    "running": true,
    "pid": 12345,
    "started_at": "2026-06-03 07:00:00"
  }
}
```

抢座结果列表：

```json
{
  "success": true,
  "message": "Seat results",
  "data": [
    {
      "seat_no": "A203",
      "reserve_time": "2026-06-04 07:30-09:30",
      "status": "success",
      "reason": "预约成功"
    }
  ]
}
```
