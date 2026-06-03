# 给前端成员 C 的接口对接说明

本文档用于前端页面快速对接 Flask API。前端不需要关心 Shell 内部实现，只需要按照下面接口发送请求，并根据统一返回格式展示成功或错误信息。

## 1. 前端请求基础配置

后端默认地址：

```text
http://localhost:5000
```

如果前端模板由 Flask 渲染，直接使用相对路径即可：

```javascript
fetch("/api/auth/login")
```

如果前端独立运行，例如 Vite / 静态服务器，则使用完整地址：

```javascript
fetch("http://localhost:5000/api/auth/login")
```

## 2. 统一请求封装建议

建议在 `frontend/static/js/main.js` 里放这个函数：

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

function showError(error) {
  alert(error.message || "操作失败");
}
```

## 3. 登录页对接

页面：

```text
frontend/templates/login.html
frontend/static/js/login.js
```

接口：

```text
POST /api/auth/login
GET  /api/auth/status
```

登录请求：

```javascript
async function login() {
  const account = document.querySelector("#account").value;
  const password = document.querySelector("#password").value;
  const email = document.querySelector("#email").value;

  try {
    await requestJSON("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ account, password, email })
    });

    window.location.href = "/dashboard";
  } catch (error) {
    showError(error);
  }
}
```

注意：

```text
email 可选，不填也可以登录。
```

## 4. 首页 / Dashboard 对接

页面：

```text
frontend/templates/dashboard.html
frontend/static/js/dashboard.js
```

推荐加载接口：

```text
GET /api/auth/status
GET /api/schedule/today
GET /api/seat/result?limit=5
GET /api/logs/error?limit=5
```

示例：

```javascript
async function loadDashboard() {
  try {
    const authStatus = await requestJSON("/api/auth/status");
    const today = await requestJSON("/api/schedule/today");
    const seatResults = await requestJSON("/api/seat/result?limit=5");
    const errors = await requestJSON("/api/logs/error?limit=5");

    console.log(authStatus, today, seatResults, errors);
  } catch (error) {
    showError(error);
  }
}
```

## 5. 日程页面对接

页面：

```text
frontend/templates/schedule.html
frontend/static/js/schedule.js
```

常用接口：

| 功能 | 方法 | 地址 |
|---|---|---|
| 同步课表 | POST | `/api/schedule/sync` |
| 同步考试 | POST | `/api/schedule/exam/sync` |
| 今日课程/待办 | GET | `/api/schedule/today` |
| 检测变动 | POST | `/api/schedule/changes/detect` |

同步课表示例：

```javascript
async function syncSchedule() {
  try {
    await requestJSON("/api/schedule/sync", { method: "POST" });
    alert("课表同步完成");
  } catch (error) {
    showError(error);
  }
}
```

## 6. DDL / 任务页面对接

页面：

```text
frontend/templates/tasks.html
frontend/static/js/tasks.js
```

新增任务：

```text
POST /api/schedule/task/add
```

请求示例：

```javascript
async function addTask() {
  const payload = {
    title: document.querySelector("#title").value,
    deadline: document.querySelector("#deadline").value,
    priority: document.querySelector("#priority").value,
    category: document.querySelector("#category").value,
    repeat_rule: document.querySelector("#repeatRule").value,
    reminder_time: document.querySelector("#reminderTime").value,
    note: document.querySelector("#note").value
  };

  try {
    await requestJSON("/api/schedule/task/add", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    alert("任务添加成功");
  } catch (error) {
    showError(error);
  }
}
```

更新任务：

```text
POST /api/schedule/task/update
```

删除任务：

```text
POST /api/schedule/task/delete
```

删除示例：

```javascript
await requestJSON("/api/schedule/task/delete", {
  method: "POST",
  body: JSON.stringify({ id: 1 })
});
```

## 7. 抢座页面对接

页面：

```text
frontend/templates/seat.html
frontend/static/js/seat.js
```

常用接口：

| 功能 | 方法 | 地址 |
|---|---|---|
| 保存配置 | POST | `/api/seat/config` |
| 检查座位 | GET | `/api/seat/check?floor=3楼&seat_no=A203` |
| 立即预约 | POST | `/api/seat/reserve` |
| 启动抢座 | POST | `/api/seat/start` |
| 查询结果 | GET | `/api/seat/result?limit=20` |

保存抢座配置：

```javascript
async function saveSeatConfig() {
  const payload = {
    floor: "3楼",
    seat_no: "A203",
    priority: 1,
    reserve_date: "2026-06-04",
    reserve_start_time: "08:00",
    reserve_end_time: "12:00",
    check_start_time: "07:55",
    check_stop_time: "08:10",
    retry_interval: 10,
    max_retry_count: 30,
    max_duration_minutes: 15,
    enabled: true
  };

  try {
    await requestJSON("/api/seat/config", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    alert("抢座配置已保存");
  } catch (error) {
    showError(error);
  }
}
```

抢座状态轮询示例：

```javascript
setInterval(async () => {
  try {
    const results = await requestJSON("/api/seat/result?limit=5");
    console.log(results);
  } catch (error) {
    console.error(error);
  }
}, 10000);
```

## 8. 日志页面对接

页面：

```text
frontend/templates/logs.html
frontend/static/js/logs.js
```

接口：

```text
GET /api/logs/list?module=seat&level=ERROR&limit=20
GET /api/logs/error?limit=20
GET /api/logs/module/auth?limit=20
```

查询日志示例：

```javascript
async function loadLogs() {
  const module = document.querySelector("#module").value;
  const level = document.querySelector("#level").value;

  try {
    const logs = await requestJSON(`/api/logs/list?module=${module}&level=${level}&limit=50`);
    console.log(logs);
  } catch (error) {
    showError(error);
  }
}
```

可选模块：

```text
auth / schedule / seat / notification / feedback / system / error
```

可选等级：

```text
DEBUG / INFO / WARNING / ERROR / CRITICAL
```

## 9. 通知设置页面对接

页面：

```text
frontend/templates/profile.html
frontend/static/js/profile.js
```

获取通知配置：

```text
GET /api/notification/settings
```

更新通知配置：

```text
POST /api/notification/settings
```

请求示例：

```javascript
await requestJSON("/api/notification/settings", {
  method: "POST",
  body: JSON.stringify({
    enable_email: true,
    enable_desktop: true,
    enable_seat_result: true,
    enable_schedule_reminder: true,
    enable_error_alert: true
  })
});
```

发送测试通知：

```text
POST /api/notification/test
```

```javascript
await requestJSON("/api/notification/test", {
  method: "POST",
  body: JSON.stringify({
    channel: "all",
    title: "CampusPilot 测试通知",
    content: "通知功能测试成功"
  })
});
```

## 10. 用户反馈页面对接

页面：

```text
frontend/templates/feedback.html
frontend/static/js/feedback.js
```

提交反馈：

```text
POST /api/feedback/submit
```

请求示例：

```javascript
async function submitFeedback() {
  const payload = {
    type: document.querySelector("#type").value,
    title: document.querySelector("#title").value,
    content: document.querySelector("#content").value,
    priority: document.querySelector("#priority").value,
    contact_email: document.querySelector("#contactEmail").value,
    include_context: document.querySelector("#includeContext").checked
  };

  try {
    await requestJSON("/api/feedback/submit", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    alert("反馈提交成功");
  } catch (error) {
    showError(error);
  }
}
```

查看反馈列表：

```text
GET /api/feedback/list
GET /api/feedback/list?status=pending
```

查看反馈详情：

```text
GET /api/feedback/1
```

反馈类型：

```text
login / schedule / seat / notification / frontend / other
```

反馈状态：

```text
pending / processing / resolved / closed
```

优先级：

```text
high / medium / low
```

## 11. 个人中心页面对接

页面：

```text
frontend/templates/profile.html
frontend/static/js/profile.js
```

获取用户配置：

```text
GET /api/user/profile
```

更新用户配置：

```text
POST /api/user/profile
```

请求示例：

```javascript
await requestJSON("/api/user/profile", {
  method: "POST",
  body: JSON.stringify({
    account: "20230001",
    password: "password",
    email: "student@example.com",
    enable_email: true,
    enable_desktop: true
  })
});
```

导出配置：

```text
POST /api/user/export
```

导入配置：

```text
POST /api/user/import
```

获取统计：

```text
GET /api/user/statistics
```

## 12. 前端错误处理建议

所有 API 都会返回 `success` 字段。前端只要判断：

```javascript
if (!data.success) {
  showError(data.message);
}
```

常见错误：

| 错误信息 | 说明 |
|---|---|
| `Missing fields: xxx` | 缺少必填字段 |
| `Invalid feedback type` | 反馈类型不合法 |
| `Invalid feedback status` | 反馈状态不合法 |
| `Invalid task priority` | 任务优先级不合法 |
| `Invalid log module` | 日志模块不合法 |
| `Shell script not found` | 成员 A 的 Shell 脚本暂未提供 |

## 13. 当前开发阶段注意事项

当前 Flask API 已经就绪，但部分 Shell 脚本可能还未由成员 A 完成。当前端调用接口时，如果 Shell 文件不存在，后端会返回：

```json
{
  "success": false,
  "message": "Shell script not found: shell/xxx/xxx.sh",
  "data": null
}
```

这说明前端请求路径和后端 API 是通的，只是 Shell 核心逻辑还没接上。

## 14. 建议页面与接口对应表

| 页面 | 主要接口 |
|---|---|
| 登录页 | `/api/auth/login`, `/api/auth/status` |
| 首页 | `/api/schedule/today`, `/api/seat/result`, `/api/logs/error` |
| 日程页 | `/api/schedule/sync`, `/api/schedule/today`, `/api/schedule/exam/sync` |
| DDL 页 | `/api/schedule/task/add`, `/api/schedule/task/update`, `/api/schedule/task/delete` |
| 抢座页 | `/api/seat/config`, `/api/seat/check`, `/api/seat/start`, `/api/seat/result` |
| 日志页 | `/api/logs/list`, `/api/logs/error`, `/api/logs/module/<module>` |
| 反馈页 | `/api/feedback/submit`, `/api/feedback/list`, `/api/feedback/<id>` |
| 个人中心 | `/api/user/profile`, `/api/notification/settings`, `/api/user/export`, `/api/user/import` |
