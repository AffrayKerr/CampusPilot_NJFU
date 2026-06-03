# CampusPilot API 文档

本文档面向后端、前端与 Shell 成员，用于说明 Flask API 层的接口约定。项目采用“前端页面 → Flask API → Shell 脚本 → SQLite / 系统服务”的架构，Flask 只负责参数接收、基础校验、调用 Shell 和返回 JSON。

## 1. 基础约定

### 1.1 服务地址

开发环境默认地址：

```text
http://localhost:5000
```

局域网访问示例：

```text
http://树莓派IP:5000
```

### 1.2 请求格式

POST 接口默认使用 JSON 请求体：

```http
Content-Type: application/json
```

### 1.3 统一返回格式

成功：

```json
{
  "success": true,
  "message": "操作成功",
  "data": {}
}
```

失败：

```json
{
  "success": false,
  "message": "错误原因",
  "data": null
}
```

### 1.4 Shell 对接约定

所有核心业务由 Shell 完成。Flask 使用 `backend/services/shell_runner.py` 调用 Shell 脚本。

Shell 脚本建议输出 JSON：

```json
{
  "success": true,
  "message": "Shell 执行成功",
  "data": {}
}
```

退出码约定：

```text
0     成功
非 0  失败
```

---

## 2. 健康检查

### GET `/api/health`

用于检测 Flask 后端是否正常运行。

响应示例：

```json
{
  "success": true,
  "message": "CampusPilot backend is running",
  "data": null
}
```

---

## 3. 登录认证 API

基础路径：

```text
/api/auth
```

### GET `/api/auth/ping`

检测认证 API 是否可用。

### POST `/api/auth/login`

WebVPN 登录。

调用 Shell：

```text
shell/auth/login.sh
```

请求：

```json
{
  "account": "校园网账号",
  "password": "校园网密码",
  "email": "可选邮箱"
}
```

必填字段：

```text
account
password
```

### GET `/api/auth/status`

检查登录态是否有效。

调用 Shell：

```text
shell/auth/check_session.sh
```

### POST `/api/auth/refresh`

刷新登录会话。

调用 Shell：

```text
shell/auth/refresh_session.sh
```

### POST `/api/auth/logout`

退出登录。

调用 Shell：

```text
shell/auth/logout.sh
```

---

## 4. 日程管理 API

基础路径：

```text
/api/schedule
```

### GET `/api/schedule/ping`

检测日程 API 是否可用。

### POST `/api/schedule/sync`

同步课程表。

调用 Shell：

```text
shell/schedule/sync_schedule.sh
```

### POST `/api/schedule/exam/sync`

同步考试安排。

调用 Shell：

```text
shell/schedule/sync_exam.sh
```

### GET `/api/schedule/today`

查询今日课程与待办。

调用 Shell：

```text
shell/schedule/list_today.sh
```

### POST `/api/schedule/changes/detect`

检测课表或考试安排变动。

调用 Shell：

```text
shell/schedule/detect_changes.sh
```

### POST `/api/schedule/task/add`

新增 DDL / 自定义任务。

调用 Shell：

```text
shell/schedule/add_task.sh
```

请求：

```json
{
  "title": "Linux 项目报告",
  "deadline": "2026-06-10 23:59",
  "priority": "high",
  "category": "项目",
  "repeat_rule": "none",
  "reminder_time": "2026-06-09 23:59",
  "note": "需要提交 PDF"
}
```

必填字段：

```text
title
deadline
```

字段说明：

| 字段 | 说明 |
|---|---|
| `priority` | `high` / `medium` / `low`，默认 `medium` |
| `category` | 学习、考试、项目、比赛等 |
| `repeat_rule` | 重复规则，可先传空字符串 |
| `reminder_time` | 自定义提醒时间 |
| `note` | 备注 |

### POST `/api/schedule/task/update`

更新 DDL / 自定义任务。

调用 Shell：

```text
shell/schedule/update_task.sh
```

请求：

```json
{
  "id": 1,
  "title": "Linux 项目报告修改版",
  "deadline": "2026-06-11 23:59",
  "priority": "medium",
  "category": "项目",
  "repeat_rule": "none",
  "reminder_time": "2026-06-10 23:59",
  "note": "更新备注",
  "status": "pending"
}
```

必填字段：

```text
id
```

`status` 可选值：

```text
pending / done / cancelled
```

### POST `/api/schedule/task/delete`

删除 DDL / 自定义任务。

调用 Shell：

```text
shell/schedule/delete_task.sh
```

请求：

```json
{
  "id": 1
}
```

---

## 5. 图书馆抢座 API

基础路径：

```text
/api/seat
```

### GET `/api/seat/ping`

检测抢座 API 是否可用。

### POST `/api/seat/config`

保存抢座配置。

调用 Shell：

```text
shell/seat/seat_config.sh
```

请求：

```json
{
  "floor": "3楼",
  "seat_no": "A203",
  "priority": 1,
  "reserve_date": "2026-06-04",
  "reserve_start_time": "08:00",
  "reserve_end_time": "12:00",
  "check_start_time": "07:55",
  "check_stop_time": "08:10",
  "retry_interval": 10,
  "max_retry_count": 30,
  "max_duration_minutes": 15,
  "enabled": true
}
```

必填字段：

```text
seat_no
```

### GET `/api/seat/check`

检查座位状态。

调用 Shell：

```text
shell/seat/check_seat.sh
```

查询参数：

```text
floor=3楼
seat_no=A203
```

示例：

```text
/api/seat/check?floor=3楼&seat_no=A203
```

### POST `/api/seat/reserve`

立即预约座位。

调用 Shell：

```text
shell/seat/reserve_seat.sh
```

请求：

```json
{
  "seat_no": "A203",
  "reserve_date": "2026-06-04",
  "reserve_start_time": "08:00",
  "reserve_end_time": "12:00"
}
```

必填字段：

```text
seat_no
```

### POST `/api/seat/start`

启动抢座任务。

调用 Shell：

```text
shell/seat/seat_worker.sh
```

### POST `/api/seat/retry`

手动触发抢座重试。

调用 Shell：

```text
shell/seat/retry_seat.sh
```

### POST `/api/seat/cancel`

取消座位预约。

调用 Shell：

```text
shell/seat/cancel_seat.sh
```

请求：

```json
{
  "seat_no": "A203"
}
```

### GET `/api/seat/result`

查询抢座结果。

调用 Shell：

```text
shell/seat/list_results.sh
```

查询参数：

```text
limit=20
```

---

## 6. 日志 API

基础路径：

```text
/api/logs
```

### GET `/api/logs/ping`

检测日志 API 是否可用。

### GET `/api/logs/list`

查询日志列表。

调用 Shell：

```text
shell/system/query_logs.sh
```

查询参数：

| 参数 | 说明 |
|---|---|
| `module` | 可选，模块名 |
| `level` | 可选，日志等级 |
| `limit` | 可选，默认 50 |

`module` 可选值：

```text
auth / schedule / seat / notification / feedback / system / error
```

`level` 可选值：

```text
DEBUG / INFO / WARNING / ERROR / CRITICAL
```

示例：

```text
/api/logs/list?module=seat&level=ERROR&limit=20
```

### GET `/api/logs/error`

查询错误日志。

查询参数：

```text
limit=50
```

### GET `/api/logs/module/<module>`

按模块查询日志。

示例：

```text
/api/logs/module/auth?limit=20
```

---

## 7. 通知 API

基础路径：

```text
/api/notification
```

### GET `/api/notification/ping`

检测通知 API 是否可用。

### GET `/api/notification/settings`

获取通知配置。

调用 Shell：

```text
shell/notification/get_settings.sh
```

### POST `/api/notification/settings`

更新通知配置。

调用 Shell：

```text
shell/notification/update_settings.sh
```

请求：

```json
{
  "enable_email": true,
  "enable_desktop": true,
  "enable_seat_result": true,
  "enable_schedule_reminder": true,
  "enable_error_alert": true
}
```

### POST `/api/notification/test`

发送测试通知。

调用 Shell：

```text
shell/notification/test_notify.sh
```

请求：

```json
{
  "channel": "all",
  "title": "CampusPilot 测试通知",
  "content": "通知功能测试成功"
}
```

`channel` 可选值：

```text
email / desktop / all
```

### POST `/api/notification/email`

发送邮件通知。

调用 Shell：

```text
shell/notification/notify_email.sh
```

请求：

```json
{
  "subject": "抢座结果通知",
  "content": "座位 A203 预约成功",
  "to": "student@example.com"
}
```

必填字段：

```text
subject
content
```

### POST `/api/notification/desktop`

发送 Linux 桌面弹窗通知。

调用 Shell：

```text
shell/notification/notify_desktop.sh
```

请求：

```json
{
  "title": "上课提醒",
  "content": "15 分钟后有操作系统课程"
}
```

必填字段：

```text
title
content
```

---

## 8. 用户反馈 API

基础路径：

```text
/api/feedback
```

### GET `/api/feedback/ping`

检测反馈 API 是否可用。

### POST `/api/feedback/submit`

提交用户反馈。

调用 Shell：

```text
shell/feedback/submit_feedback.sh
```

请求：

```json
{
  "type": "seat",
  "title": "抢座失败后没有通知",
  "content": "今天早上抢座失败，但系统没有发送邮件通知。",
  "contact_email": "student@example.com",
  "priority": "medium",
  "include_context": true
}
```

必填字段：

```text
type
title
content
```

`type` 可选值：

```text
login / schedule / seat / notification / frontend / other
```

`priority` 可选值：

```text
high / medium / low
```

### GET `/api/feedback/list`

查询反馈列表。

调用 Shell：

```text
shell/feedback/list_feedback.sh
```

查询参数：

```text
status=pending
```

`status` 可选值：

```text
pending / processing / resolved / closed
```

### GET `/api/feedback/<id>`

查询反馈详情。

调用 Shell：

```text
shell/feedback/get_feedback.sh
```

示例：

```text
/api/feedback/1
```

### POST `/api/feedback/update`

更新反馈状态。

调用 Shell：

```text
shell/feedback/update_feedback.sh
```

请求：

```json
{
  "id": 1,
  "status": "processing",
  "message": "已开始排查"
}
```

必填字段：

```text
id
status
```

### POST `/api/feedback/close`

关闭反馈。

调用 Shell：

```text
shell/feedback/close_feedback.sh
```

请求：

```json
{
  "id": 1,
  "message": "问题已解决"
}
```

必填字段：

```text
id
```

---

## 9. 用户中心 API

基础路径：

```text
/api/user
```

### GET `/api/user/ping`

检测用户中心 API 是否可用。

### GET `/api/user/profile`

获取用户配置。

调用 Shell：

```text
shell/user/get_profile.sh
```

### POST `/api/user/profile`

更新用户配置。

调用 Shell：

```text
shell/user/update_profile.sh
```

请求：

```json
{
  "account": "校园网账号",
  "password": "校园网密码",
  "email": "student@example.com",
  "enable_email": true,
  "enable_desktop": true
}
```

必填字段：

```text
account
password
```

说明：

```text
email 可选；为空时不启用邮件相关能力。
```

### POST `/api/user/export`

导出用户配置。

调用 Shell：

```text
shell/user/export_config.sh
```

请求：

```json
{
  "export_path": "config/export.json"
}
```

### POST `/api/user/import`

导入用户配置。

调用 Shell：

```text
shell/user/import_config.sh
```

请求：

```json
{
  "import_path": "config/export.json"
}
```

必填字段：

```text
import_path
```

### GET `/api/user/statistics`

获取用户统计信息。

调用 Shell：

```text
shell/user/get_statistics.sh
```

---

## 10. 常见错误响应

### 缺少字段

```json
{
  "success": false,
  "message": "Missing fields: account, password",
  "data": null
}
```

### 参数非法

```json
{
  "success": false,
  "message": "Invalid feedback type",
  "data": null
}
```

### Shell 脚本不存在

```json
{
  "success": false,
  "message": "Shell script not found: shell/auth/login.sh",
  "data": null
}
```

### Shell 执行超时

```json
{
  "success": false,
  "message": "Shell script execution timeout",
  "data": null
}
```

---

## 11. 前后端对接建议

前端统一封装请求函数：

```javascript
async function requestJSON(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.message || "请求失败");
  }

  return data.data;
}
```

POST 示例：

```javascript
await requestJSON("/api/auth/login", {
  method: "POST",
  body: JSON.stringify({
    account: "20230001",
    password: "password",
    email: "student@example.com"
  })
});
```

GET 示例：

```javascript
const today = await requestJSON("/api/schedule/today");
```
