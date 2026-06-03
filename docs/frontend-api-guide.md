# 给前端成员 C 的接口对接说明

本文档用于前端快速对接 Flask API。前端不需要关心 Shell 内部实现，只需按统一响应格式处理成功和错误。

## 1. 请求基础配置

后端默认地址：

```text
http://localhost:5000
```

Flask 模板页面可直接使用相对路径：

```javascript
fetch("/api/account/login")
```

独立前端服务使用完整地址：

```javascript
fetch("http://localhost:5000/api/account/login")
```

## 2. 统一请求封装

登录成功后保存 token：

```javascript
localStorage.setItem("campuspilot_token", data.token);
```

推荐请求函数：

```javascript
async function requestJSON(url, options = {}) {
  const token = localStorage.getItem("campuspilot_token");

  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {})
    },
    ...options
  });

  const data = await response.json();

  if (!data.success) {
    if (data.message === "Authentication required") {
      localStorage.removeItem("campuspilot_token");
      window.location.href = "/";
      return;
    }
    throw new Error(data.message || "请求失败");
  }

  return data.data;
}

function showError(error) {
  alert(error.message || "操作失败");
}
```

## 3. 用户流程

普通用户流程：

```text
注册 CampusPilot 账号
  ↓
登录并保存 token
  ↓
进入个人中心
  ↓
绑定校园网账号
  ↓
同步课表 / 考试 / 抢座
```

如果未绑定校园网账号调用课表同步或抢座接口，后端返回：

```text
Campus account is not bound
```

前端应提示：

```text
请先到个人中心绑定校园网账号
```

管理员账号由后台脚本创建，不允许前端注册 admin。

## 4. 登录 / 注册页面

注册：

```javascript
await requestJSON("/api/account/register", {
  method: "POST",
  body: JSON.stringify({
    username: "student01",
    password: "secret123",
    email: "student@example.com"
  })
});
```

登录：

```javascript
const data = await requestJSON("/api/account/login", {
  method: "POST",
  body: JSON.stringify({ username: "student01", password: "secret123" })
});

localStorage.setItem("campuspilot_token", data.token);
localStorage.setItem("campuspilot_user", JSON.stringify(data.user));
```

查看当前用户：

```javascript
const user = await requestJSON("/api/account/me");
```

注销：

```javascript
await requestJSON("/api/account/logout", { method: "POST" });
localStorage.removeItem("campuspilot_token");
```

## 5. 个人中心页面

推荐加载：

```text
GET /api/user/profile
GET /api/user/statistics
GET /api/campus/status
GET /api/notification/settings
GET /api/reminder/list
```

修改邮箱：

```javascript
await requestJSON("/api/user/profile", {
  method: "POST",
  body: JSON.stringify({
    email: "new@example.com",
    enable_email: true,
    enable_desktop: true
  })
});
```

个人统计：

```javascript
const statistics = await requestJSON("/api/user/statistics");
```

统计数据包含：

```text
校园网绑定状态
课程数
考试数
DDL 完成率
抢座成功数
提醒数
错误日志数
```

## 6. 校园网账号绑定页面

绑定：

```javascript
await requestJSON("/api/campus/bind", {
  method: "POST",
  body: JSON.stringify({
    campus_account: "20230001",
    campus_password: "password"
  })
});
```

更新：

```javascript
await requestJSON("/api/campus/update", {
  method: "POST",
  body: JSON.stringify({
    campus_account: "20230001",
    campus_password: "new-password"
  })
});
```

解绑：

```javascript
await requestJSON("/api/campus/unbind", { method: "POST" });
```

## 7. 日程页面

常用接口：

| 功能 | 方法 | 地址 |
|---|---|---|
| 同步课表 | POST | `/api/schedule/sync` |
| 同步考试 | POST | `/api/schedule/exam/sync` |
| 检测变动 | POST | `/api/schedule/changes/detect` |
| 今日课程/待办 | GET | `/api/schedule/today` |

同步课表：

```javascript
try {
  await requestJSON("/api/schedule/sync", { method: "POST" });
  alert("课表同步完成");
} catch (error) {
  if (error.message === "Campus account is not bound") {
    alert("请先绑定校园网账号");
  } else {
    showError(error);
  }
}
```

## 8. DDL / 任务页面

新增 DDL：

```javascript
await requestJSON("/api/schedule/task/add", {
  method: "POST",
  body: JSON.stringify({
    title: "Linux 项目报告",
    deadline: "2026-06-10 23:59",
    priority: "high",
    category: "项目",
    repeat_rule: "none",
    reminder_time: "2026-06-09 23:59",
    note: "需要提交 PDF"
  })
});
```

更新：

```javascript
await requestJSON("/api/schedule/task/update", {
  method: "POST",
  body: JSON.stringify({ id: 1, status: "done" })
});
```

删除：

```javascript
await requestJSON("/api/schedule/task/delete", {
  method: "POST",
  body: JSON.stringify({ id: 1 })
});
```

## 9. 提醒设置页面

获取通知设置：

```javascript
const settings = await requestJSON("/api/notification/settings");
```

更新默认提醒：

```javascript
await requestJSON("/api/notification/settings", {
  method: "POST",
  body: JSON.stringify({
    enable_email: true,
    enable_desktop: true,
    schedule_default_reminders: [15],
    exam_default_reminders: [1440, 120],
    task_default_reminders: [1440, 120]
  })
});
```

添加单条提醒：

```javascript
await requestJSON("/api/reminder/add", {
  method: "POST",
  body: JSON.stringify({
    target_type: "exam",
    target_id: 3,
    remind_before_minutes: 1440,
    enabled: true
  })
});
```

更新提醒：

```javascript
await requestJSON("/api/reminder/update", {
  method: "POST",
  body: JSON.stringify({ id: 8, remind_before_minutes: 120, enabled: true })
});
```

应用默认提醒：

```javascript
await requestJSON("/api/reminder/defaults/apply", {
  method: "POST",
  body: JSON.stringify({ target_type: "exam" })
});
```

## 10. 抢座页面

常用接口：

| 功能 | 方法 | 地址 |
|---|---|---|
| 添加候选座位 | POST | `/api/seat/config` |
| 查看候选座位 | GET | `/api/seat/config/list` |
| 更新候选座位 | POST | `/api/seat/config/update` |
| 删除候选座位 | POST | `/api/seat/config/delete` |
| 启动抢座 | POST | `/api/seat/start` |
| 停止抢座 | POST | `/api/seat/stop` |
| 查看状态 | GET | `/api/seat/status` |
| 查看结果 | GET | `/api/seat/result?limit=20` |

添加候选座位：

```javascript
await requestJSON("/api/seat/config", {
  method: "POST",
  body: JSON.stringify({
    floor: "3F",
    seat_no: "A203",
    priority: 1,
    reserve_date: "2026-06-08",
    reserve_time_slots: [
      { start_time: "07:30", end_time: "09:30" },
      { start_time: "19:00", end_time: "22:00" }
    ],
    check_start_time: "07:00",
    check_stop_time: "08:10",
    retry_interval: 10,
    max_retry_count: 30,
    max_duration_minutes: 15,
    enabled: true
  })
});
```

前端校验建议：

```text
每个时间段至少 2 小时
周五 07:30-20:00
其他开放日 07:30-22:00
```

即使前端不校验，后端也会校验。

## 11. 日志页面

```javascript
const logs = await requestJSON("/api/logs/list?limit=50");
const errors = await requestJSON("/api/logs/error?limit=20");
```

## 12. 反馈页面

提交反馈：

```javascript
await requestJSON("/api/feedback/submit", {
  method: "POST",
  body: JSON.stringify({
    type: "seat",
    title: "抢座失败",
    content: "启动后没有结果",
    priority: "medium",
    contact_email: "student@example.com"
  })
});
```

查看自己的反馈：

```javascript
const feedbacks = await requestJSON("/api/feedback/list");
```

## 13. 管理员后台

管理员登录后根据：

```javascript
user.role === "admin"
```

显示管理员入口。

常用接口：

```text
GET /api/admin/users
GET /api/admin/statistics
GET /api/admin/feedback/list
GET /api/admin/feedback/{id}
POST /api/admin/feedback/update
GET /api/admin/logs/error
GET/POST /api/admin/settings/feedback-email
```

更新反馈状态：

```javascript
await requestJSON("/api/admin/feedback/update", {
  method: "POST",
  body: JSON.stringify({
    id: 1,
    status: "processing",
    message: "已收到，正在处理"
  })
});
```
