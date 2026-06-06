# Session 自动保活功能

## 概述

用户第一次通过交互式登录后，系统会自动保持 WebVPN session 在线，无需再次手动登录。

## 工作原理

`session_keeper.sh` 定期检查 session 状态：

1. **Session 有效** → 什么都不做，用户无感知
2. **Session 失效** → 尝试用保存的账号密码自动重新登录
3. **自动登录成功** → 更新 cookie，用户无感知
4. **自动登录失败**（触发验证码）→ 写入 `needs_relogin` 标记，发送桌面通知

## API 接口

基础路径：`/api/auth`

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/keep-alive` | 登录+绑定 | 手动触发一次 session 保活检查 |
| GET | `/relogin-status` | 登录+绑定 | 查询是否需要重新交互式登录 |

### GET /api/auth/relogin-status

返回示例：

```json
{
  "success": true,
  "message": "Relogin status",
  "data": {
    "needs_relogin": false,
    "session_valid": true,
    "flagged_at": null
  }
}
```

当 `needs_relogin` 为 `true` 时，前端应显示提示引导用户重新交互式登录。

### POST /api/auth/keep-alive

手动触发一次保活检查，返回 session 当前状态。

## 部署配置

### Crontab 自动保活（推荐）

每小时自动检查一次 session：

```bash
0 * * * * bash /path/to/CampusPilot/shell/auth/session_keeper.sh <user_id>
```

### 多用户配置

如果有多个用户，需要为每个用户配置独立的 cron 任务：

```bash
0 * * * * bash /path/to/CampusPilot/shell/auth/session_keeper.sh user1
15 * * * * bash /path/to/CampusPilot/shell/auth/session_keeper.sh user2
30 * * * * bash /path/to/CampusPilot/shell/auth/session_keeper.sh user3
```

或者创建一个包装脚本遍历所有用户。

## 前端集成建议

1. **页面加载时检查状态**

```javascript
async function checkReloginStatus() {
  const response = await fetch('/api/auth/relogin-status');
  const data = await response.json();
  
  if (data.data.needs_relogin) {
    showReloginBanner();
  }
}
```

2. **显示提示横幅**

当 `needs_relogin = true` 时，在页面顶部显示提示：

> WebVPN 登录已过期，需要重新登录。[立即登录]

3. **重新登录按钮**

点击后调用交互式登录接口：

```javascript
async function relogin() {
  const response = await fetch('/api/auth/bind-interactive', {
    method: 'POST'
  });
  const data = await response.json();
  
  if (data.success) {
    hideReloginBanner();
    checkReloginStatus();
  }
}
```

## Shell 脚本调用

直接调用 `session_keeper.sh`：

```bash
bash shell/auth/session_keeper.sh <user_id>
```

返回 JSON 示例：

```json
{"success": true, "message": "Session is valid", "data": {"status": "valid"}}
{"success": true, "message": "Session renewed silently", "data": {"status": "renewed"}}
{"success": false, "message": "Session expired and silent relogin failed; interactive relogin required", "data": {"status": "needs_relogin"}}
```

## 状态文件

- `runtime/users/<user_id>/needs_relogin` — 当自动登录失败时创建此文件，内容为时间戳
- `runtime/users/<user_id>/session_keeper.lock` — 防止同一用户的多个保活进程并发运行

## 日志

所有保活行为都会写入日志：

- 成功保持在线：`INFO auth "session keeper: session still valid"`
- 自动续期成功：`INFO auth "session keeper: silent relogin succeeded"`
- 需要重新登录：`WARNING auth "session keeper: silent relogin failed, user interaction required"`
