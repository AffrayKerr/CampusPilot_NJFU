# CampusPilot API 文档

本文档说明 Flask API 层接口。当前架构为：前端页面 → Flask API → Shell 脚本/数据库 → SQLite。Flask 负责登录鉴权、参数校验、用户隔离、部分统计与配置管理；爬虫、抢座 worker、通知 worker 等执行逻辑由 Shell 负责。

## 1. 基础约定

- 开发地址：`http://localhost:5000`
- 请求格式：`Content-Type: application/json`
- 登录态：优先使用 `Authorization: Bearer <token>`，也支持登录接口写入的 HttpOnly Cookie。
- 普通业务数据均按 `user_id` 隔离。

统一响应：

```json
{
  "success": true,
  "message": "操作结果",
  "data": {}
}
```

错误响应：

```json
{
  "success": false,
  "message": "错误原因",
  "data": null
}
```

常见错误：

| HTTP | message | 含义 |
|---|---|---|
| 401 | `Authentication required` | 未登录 |
| 403 | `Admin permission required` | 不是管理员 |
| 400 | `Campus account is not bound` | 未绑定校园网账号 |

## 2. 账号与登录

基础路径：`/api/account`

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/ping` | 无 | 健康检查 |
| POST | `/register` | 无 | 注册普通用户，永远创建 `user` |
| POST | `/login` | 无 | 登录 CampusPilot |
| POST | `/logout` | 可选 | 注销当前 session |
| GET | `/me` | 登录 | 查看当前用户 |
| POST | `/change-password` | 登录 | 修改密码 |

登录请求：

```json
{
  "username": "student01",
  "password": "secret123"
}
```

登录返回：

```json
{
  "token": "...",
  "expires_at": "2026-06-04T12:00:00",
  "user": {
    "id": 1,
    "username": "student01",
    "email": "student@example.com",
    "role": "user"
  }
}
```

管理员账号不允许前端注册，使用后台脚本创建：

```powershell
python backend\scripts\create_admin.py --username admin --password Admin123456 --email admin@example.com
```

## 3. 校园网账号绑定

基础路径：`/api/campus`

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/ping` | 无 | 健康检查 |
| POST | `/bind` | 登录 | 绑定校园网账号 |
| GET | `/status` | 登录 | 查看绑定状态 |
| POST | `/update` | 登录 | 更新校园网账号/密码 |
| POST | `/unbind` | 登录 | 解绑校园网账号 |
| POST | `/webvpn-login` | 登录+绑定 | 使用绑定账号触发 WebVPN 登录 |

绑定请求：

```json
{
  "campus_account": "20230001",
  "campus_password": "password"
}
```

校园网密码会加密存储。同步课表、考试、WebVPN、抢座等学校服务必须先绑定校园网账号。

## 4. WebVPN 登录态

基础路径：`/api/auth`

| 方法 | 路径 | 权限 | Shell |
|---|---|---|---|
| GET | `/ping` | 无 | - |
| POST | `/login` | 登录+绑定 | `shell/auth/login_bound.sh user_id` |
| POST | `/bind-interactive` | 登录+绑定 | `shell/auth/bind_webvpn_interactive.sh user_id` |
| GET | `/status` | 登录+绑定 | `shell/auth/check_session.sh user_id` |
| POST | `/refresh` | 登录+绑定 | `shell/auth/refresh_session.sh user_id` |
| POST | `/logout` | 登录+绑定 | `shell/auth/logout.sh user_id` |

### 4.1 交互式登录 `/bind-interactive`

**功能：** 启动本地浏览器，用户手动完成 WebVPN 登录，系统自动提取 cookie。

**请求：** 无需 body

**响应：**

```json
{
  "success": true,
  "message": "interactive login completed",
  "data": {
    "cookie_count": 2,
    "cookie_file": "D:\\...\\webvpn.cookie",
    "final_url": "https://webvpn.njfu.edu.cn/frontend_static/frontend/login/index.html#/"
  }
}
```

**说明：**

- 使用 Selenium 启动浏览器自动打开 `https://webvpn.njfu.edu.cn`
- 用户在浏览器中手动完成登录（可解决验证码问题）
- 系统自动检测登录成功并提取 cookie
- Cookie 自动保存到 `runtime/users/<user_id>/webvpn.cookie`
- 超时时间：600 秒（10 分钟）
- 依赖：需要安装 `selenium` 和 Chrome 浏览器

## 5. 日程与 DDL

基础路径：`/api/schedule`

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/ping` | 无 | 健康检查 |
| POST | `/sync` | 登录+绑定 | 同步课表 |
| POST | `/exam/sync` | 登录+绑定 | 同步考试 |
| POST | `/changes/detect` | 登录+绑定 | 检测课表/考试变动 |
| GET | `/today` | 登录 | 今日课程/待办 |
| POST | `/task/add` | 登录 | 新增 DDL |
| POST | `/task/update` | 登录 | 更新 DDL |
| POST | `/task/delete` | 登录 | 删除 DDL |

新增 DDL：

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

`priority` 支持：`high` / `medium` / `low`。

## 6. 提醒模块

### 6.1 通知设置

基础路径：`/api/notification`

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/settings` | 登录 | 获取通知与默认提醒设置 |
| POST | `/settings` | 登录 | 更新通知与默认提醒设置 |
| POST | `/test` | 登录 | 测试通知 |
| POST | `/email` | 登录 | 发送邮件通知 |
| POST | `/desktop` | 登录 | 发送桌面通知 |

通知设置示例：

```json
{
  "enable_email": true,
  "enable_desktop": true,
  "enable_seat_result": true,
  "enable_schedule_reminder": true,
  "enable_error_alert": true,
  "schedule_default_reminders": [15],
  "exam_default_reminders": [1440, 120],
  "task_default_reminders": [1440, 120]
}
```

单位均为分钟。`1440` 表示提前 1 天。

### 6.2 单条提醒

基础路径：`/api/reminder`

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/ping` | 无 | 健康检查 |
| GET | `/list` | 登录 | 查看提醒列表，可传 `target_type` |
| POST | `/add` | 登录 | 添加提醒 |
| POST | `/update` | 登录 | 更新提醒 |
| POST | `/delete` | 登录 | 删除提醒 |
| POST | `/defaults/apply` | 登录 | 给已有课程/考试/DDL 应用默认提醒 |
| POST | `/trigger` | 登录 | 手动触发一次提醒检查 |

添加提醒：

```json
{
  "target_type": "exam",
  "target_id": 3,
  "remind_before_minutes": 1440,
  "enabled": true
}
```

`target_type` 支持：`schedule` / `exam` / `task`。

## 7. 图书馆抢座

基础路径：`/api/seat`。除 `/ping` 外全部要求登录且绑定校园网账号。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/ping` | 健康检查 |
| POST | `/config` | 添加候选座位配置 |
| GET | `/config/list` | 查看候选座位配置 |
| POST | `/config/update` | 更新候选座位配置 |
| POST | `/config/delete` | 删除候选座位配置 |
| GET | `/check` | 检查座位状态 |
| POST | `/reserve` | 立即预约 |
| POST | `/start` | 启动当前用户抢座 worker |
| POST | `/stop` | 停止当前用户抢座 worker |
| GET | `/status` | 查看当前用户 worker 状态 |
| POST | `/retry` | 手动重试 |
| POST | `/cancel` | 取消预约 |
| GET | `/result` | 查看抢座结果 |

添加候选座位配置：

```json
{
  "floor": "3F",
  "seat_no": "A203",
  "priority": 1,
  "reserve_date": "2026-06-08",
  "reserve_time_slots": [
    {"start_time": "07:30", "end_time": "09:30"},
    {"start_time": "19:00", "end_time": "22:00"}
  ],
  "check_start_time": "07:00",
  "check_stop_time": "08:10",
  "retry_interval": 10,
  "max_retry_count": 30,
  "max_duration_minutes": 15,
  "enabled": true
}
```

时间规则：

- 每个预约时间段至少 2 小时。
- 周一到周四、周六、周日：`07:30-22:00`。
- 周五：`07:30-20:00`。
- 支持多个候选座位，Shell 应按 `priority ASC` 依次尝试。

## 8. 日志

基础路径：`/api/logs`

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/ping` | 无 | 健康检查 |
| GET | `/list` | 登录 | 查询当前用户日志 |
| GET | `/error` | 登录 | 查询当前用户错误日志 |
| GET | `/module/<module>` | 登录 | 按模块查询日志 |

## 9. 反馈与管理员

用户反馈基础路径：`/api/feedback`。

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/submit` | 可匿名 | 提交反馈 |
| GET | `/list` | 登录 | 查看自己的反馈 |
| GET | `/<id>` | 登录 | 查看自己的反馈详情 |
| POST | `/update` | 登录 | 更新自己的反馈 |
| POST | `/close` | 登录 | 关闭自己的反馈 |

管理员基础路径：`/api/admin`，全部要求 `role=admin`。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/users` | 用户列表 |
| GET | `/statistics` | 系统统计 |
| GET/POST | `/settings/feedback-email` | 管理反馈接收邮箱 |
| GET | `/feedback/list` | 全部反馈列表 |
| GET | `/feedback/<id>` | 反馈详情 |
| POST | `/feedback/update` | 更新反馈状态 |
| GET | `/logs` | 全局日志 |
| GET | `/logs/error` | 全局错误日志 |

## 10. 个人中心

基础路径：`/api/user`

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/profile` | 登录 | 查看资料 |
| POST | `/profile` | 登录 | 修改邮箱和基础通知开关 |
| POST | `/export` | 登录 | 导出配置，当前调用 Shell |
| POST | `/import` | 登录 | 导入配置，当前调用 Shell |
| GET | `/statistics` | 登录 | Flask 直接统计个人数据 |

`/api/user/statistics` 返回课程数、考试数、DDL 完成率、抢座成功数、提醒数、错误日志数、校园网绑定状态等，可直接用于个人中心统计卡片。


### 5.1 自动同步课表

Shell 脚本: shell/schedule/auto_sync.sh user_id [interval_days]

功能：检查距离上次课表同步是否超过指定天数（默认 7 天），若超过则自动触发 sync_schedule.sh。

建议通过 cron 定时任务每天运行此脚本，实现课表定期自动更新。

crontab 示例：

`ash
# 每天凌晨 3 点检查所有用户的课表是否需要同步
0 3 * * * bash /path/to/CampusPilot/shell/schedule/auto_sync.sh user_id 7
`
