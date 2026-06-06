# 图书馆抢座模块设计文档

## 1. 模块概述

图书馆抢座模块实现了南京林业大学图书馆座位预约系统的自动化预约功能。用户可以配置候选座位、预约时间段、重试策略，系统会在指定时间自动抢座并通知结果。

## 2. 技术架构

### 2.1 架构层次

```
前端 (Web UI)
    ↓
Flask API 层 (backend/api/seat_api.py)
    ↓
Shell 脚本层 (shell/seat/*.sh)
    ↓
Python 核心逻辑 (shell/seat/seat_client.py)
    ↓
图书馆系统 API (libseat.njfu.edu.cn via WebVPN)
```

### 2.2 核心组件

| 组件类型 | 文件 | 职责 |
|---------|------|------|
| Flask API | `backend/api/seat_api.py` | 处理前端请求、参数校验、用户隔离 |
| Shell 配置管理 | `shell/seat/seat_config.sh`<br>`shell/seat/list_configs.sh`<br>`shell/seat/update_config.sh`<br>`shell/seat/delete_config.sh` | 座位配置的增删改查 |
| Shell Worker 管理 | `shell/seat/start_worker.sh`<br>`shell/seat/stop_worker.sh`<br>`shell/seat/worker_status.sh`<br>`shell/seat/seat_worker.sh` | 后台抢座任务管理 |
| Shell 预约操作 | `shell/seat/reserve_seat.sh`<br>`shell/seat/check_seat.sh`<br>`shell/seat/cancel_seat.sh`<br>`shell/seat/retry_seat.sh` | 座位预约核心操作 |
| Python 核心逻辑 | `shell/seat/seat_client.py` | 实现图书馆 API 调用、重试逻辑、状态管理 |
| 数据库表 | `seat_configs`<br>`seat_results` | 配置存储和结果记录 |

## 3. 图书馆系统 API 分析

### 3.1 认证机制

图书馆系统使用独立的 token 认证，与 WebVPN cookie 分离：

1. **SSO 入口**: `https://webvpn.njfu.edu.cn/rump_frontend/connect/?target=Library&id=12`
2. **认证流程**:
   - 用 WebVPN cookie 访问 SSO 入口
   - 自动跳转到图书馆系统并完成登录
   - 图书馆系统返回 `token`（存储在浏览器 localStorage）
3. **后续请求**: 所有 API 请求需携带 `token` 请求头

### 3.2 核心 API 端点

基础路径: `https://webvpn.njfu.edu.cn/webvpn/.../ic-web/`

#### 3.2.1 查询座位状态

```http
GET /ic-web/reserve?vpn-12-libseat.njfu.edu.cn&roomIds={roomId}&resvDates={yyyyMMdd}&sysKind=8
Headers:
  token: {library_token}
```

**响应示例**:
```json
{
  "code": 0,
  "message": "查询成功",
  "data": [
    {
      "devId": 100500005,
      "devName": "4F-A161",
      "devStatus": 0,
      "openStart": "07:30",
      "openEnd": "22:00",
      "resvInfo": []
    }
  ]
}
```

**说明**:
- `devId`: 座位数字 ID（预约时使用）
- `devName`: 座位名称（如 `4F-A161`，用户配置时使用）
- `devStatus`: 0=空闲, 1=占用, 2=临时离开

#### 3.2.2 预约座位

```http
POST /ic-web/reserve?vpn-12-libseat.njfu.edu.cn
Headers:
  token: {library_token}
  Content-Type: application/json;charset=UTF-8
Body:
{
  "sysKind": 8,
  "appAccNo": 143924891,
  "memberKind": 1,
  "resvMember": [143924891],
  "resvBeginTime": "2026-06-07 07:30:00",
  "resvEndTime": "2026-06-07 22:00:00",
  "testName": "",
  "captcha": "",
  "resvProperty": 0,
  "resvDev": [100500005],
  "memo": ""
}
```

**响应示例**:
```json
{
  "code": 0,
  "message": "预约成功",
  "data": {
    "uuid": "38fa8f3cb740409cac74522a4af62706",
    "resvId": 146755977,
    "resvStatus": 1027
  }
}
```

**说明**:
- `appAccNo`: 用户在图书馆系统的账号 ID
- `resvDev`: 座位的 `devId` 数组（支持多座位，但通常只预约一个）
- `uuid`: 预约记录的唯一标识（取消时使用）

#### 3.2.3 取消预约

```http
POST /ic-web/reserve/delete?vpn-12-libseat.njfu.edu.cn
Headers:
  token: {library_token}
  Content-Type: application/json;charset=UTF-8
Body:
{
  "uuid": "38fa8f3cb740409cac74522a4af62706"
}
```

**响应示例**:
```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

### 3.3 开放时间规则

根据星期几的不同，图书馆开放时间有差异：

| 星期 | 开放时间 |
|-----|---------|
| 星期一至四 | 07:30 - 22:00 |
| 星期五 | 07:30 - 20:00 |
| 星期六至日 | 07:30 - 22:00 |

**实现位置**: Flask API 已在 `backend/api/seat_api.py` 中实现时间校验。

### 3.4 预约规则

可在前一天00:00预约所需座位。预约时长最短2小时，最长15小时。座位可预约时间为当日的当前时间至闭馆时间，次日的开馆时间至闭馆时间

## 4. 数据库设计

### 4.1 座位配置表 (seat_configs)

```sql
CREATE TABLE seat_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    floor TEXT,
    seat_no TEXT NOT NULL,
    priority INTEGER DEFAULT 1,
    reserve_date TEXT,
    reserve_start_time TEXT,
    reserve_end_time TEXT,
    reserve_time_slots TEXT,
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
```

**字段说明**:
- `seat_no`: 座位名称，如 `4F-A161`
- `priority`: 优先级，数字越小优先级越高
- `reserve_time_slots`: JSON 数组，支持多时间段预约，如 `[{"start_time":"07:30","end_time":"09:30"},{"start_time":"19:00","end_time":"22:00"}]`
- `check_start_time`/`check_stop_time`: Worker 运行时间窗口
- `retry_interval`: 失败后重试间隔（秒）
- `max_retry_count`: 最大重试次数
- `max_duration_minutes`: Worker 最大运行时长（分钟）

### 4.2 抢座结果表 (seat_results)

```sql
CREATE TABLE seat_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    seat_no TEXT,
    reserve_time TEXT,
    status TEXT NOT NULL,
    reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**字段说明**:
- `status`: `success` / `failed` / `error`
- `reason`: 结果原因（成功/失败消息）
- `reserve_time`: 预约时间段，如 `2026-06-07 07:30-22:00`

## 5. 工作流程

### 5.1 配置流程

```
1. 用户在前端配置候选座位
   ├─ 座位名称 (如 4F-A161)
   ├─ 预约日期和时间段
   ├─ 检查时间窗口
   └─ 重试策略

2. Flask API 校验参数
   ├─ 时间段至少 2 小时
   ├─ 不超过图书馆开放时间
   └─ 按 priority 排序

3. Shell 脚本写入数据库
   └─ INSERT INTO seat_configs
```

### 5.2 手动预约流程

```
用户点击"立即预约"
    ↓
POST /api/seat/reserve
    ↓
shell/seat/reserve_seat.sh
    ↓
seat_client.py reserve
    ├─ 1. 获取图书馆 token
    ├─ 2. 查询座位 devId (通过 devName)
    ├─ 3. 调用预约 API
    ├─ 4. 保存结果到 seat_results
    └─ 5. 写日志到 logs 表
```

### 5.3 自动抢座流程 (Worker)

```
用户点击"启动抢座"
    ↓
POST /api/seat/start
    ↓
shell/seat/start_worker.sh
    ├─ 检查 PID 文件
    ├─ 后台启动 seat_worker.sh
    └─ 记录 PID

seat_worker.sh 循环执行:
    ├─ 查询 enabled=1 的配置 (按 priority 排序)
    ├─ 检查是否在时间窗口内
    ├─ 遍历每个候选座位
    │   ├─ 遍历每个时间段
    │   ├─ 调用预约 API
    │   ├─ 成功 → 记录结果，退出
    │   └─ 失败 → 等待 retry_interval 秒后重试
    ├─ 达到 max_retry_count → 下一个座位
    └─ 达到 max_duration_minutes → 退出

用户点击"停止抢座"
    ↓
POST /api/seat/stop
    ↓
shell/seat/stop_worker.sh
    ├─ 读取 PID
    ├─ kill 进程
    └─ 清理 PID 文件
```

## 6. 当前实现状态

### 6.1 已完成部分

✅ **Flask API 层** (`backend/api/seat_api.py`)
- 完整的 RESTful 接口
- 参数校验（时间、时长、开放时间）
- 用户隔离和权限控制

✅ **Shell 脚本层** (`shell/seat/*.sh`)
- 配置管理：增删改查全部实现
- Worker 管理：启动、停止、状态查询
- 预约操作：预约、取消、重试、检查

✅ **数据库操作**
- 所有配置写入、查询逻辑完整
- 结果记录和日志功能完整

✅ **框架代码** (`shell/seat/seat_client.py`)
- 完整的函数框架
- 重试逻辑
- 时间窗口检查
- 多座位轮询
- 多时间段支持

### 6.2 待实现部分（需要补充真实 API 调用）

⚠️ **认证部分**
```python
def get_library_token(session):
    """需要实现：
    1. 访问 /rump_frontend/connect/?target=Library&id=12
    2. 跟随 SSO 跳转
    3. 从响应或浏览器上下文提取 token
    4. 缓存 token 到文件（避免频繁登录）
    """
    pass

def get_user_app_acc_no(session, token):
    """需要实现：
    获取用户在图书馆系统的 appAccNo
    可能需要调用 /ic-web/user/info 或类似接口
    """
    pass
```

⚠️ **座位查询**
```python
def check_seat_status(session, floor, seat_no):
    """需要实现：
    1. 调用 GET /ic-web/reserve?roomIds=...&resvDates=...&sysKind=8
    2. 从返回的座位列表中找到 devName == seat_no 的座位
    3. 返回 devId 和 devStatus
    """
    pass
```

⚠️ **预约和取消**
```python
def reserve_seat(session, seat_no, reserve_date, start_time, end_time):
    """需要实现：
    1. 先查询座位获取 devId
    2. 获取 token 和 appAccNo
    3. 构造请求 body
    4. POST /ic-web/reserve
    5. 解析响应，返回 uuid 和状态
    """
    pass

def cancel_seat_reservation(session, seat_no):
    """需要实现：
    1. 查询当前用户的预约列表
    2. 找到 seat_no 对应的 uuid
    3. POST /ic-web/reserve/delete
    """
    pass
```

### 6.3 实现方案建议

**方案 A：Selenium 方案（推荐）**

优点：
- 可以从浏览器 localStorage 读取 token
- 可以处理任何 JavaScript 动态生成的内容
- 项目已有先例（`schedule_scraper.py`）

缺点：
- 需要浏览器环境
- 首次获取 token 较慢（约 10-20 秒）

实现步骤：
```python
from selenium import webdriver

def get_library_token_selenium(user_id):
    driver = webdriver.Chrome(options=chrome_options)
    driver.get("https://webvpn.njfu.edu.cn/rump_frontend/connect/?target=Library&id=12")
    time.sleep(5)
    token = driver.execute_script("return localStorage.getItem('token')")
    driver.quit()
    return token
```

**方案 B：纯 requests 方案**

优点：
- 不需要浏览器
- 速度快

缺点：
- 需要分析 SSO 跳转链路
- token 生成逻辑可能复杂
- 可能有反爬机制

## 7. 使用示例

### 7.1 API 调用示例

```bash
# 添加座位配置
curl -X POST http://localhost:5000/api/seat/config \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "floor": "4F",
    "seat_no": "4F-A161",
    "priority": 1,
    "reserve_date": "2026-06-08",
    "reserve_time_slots": [
      {"start_time": "07:30", "end_time": "09:30"},
      {"start_time": "19:00", "end_time": "22:00"}
    ],
    "check_start_time": "07:00",
    "check_stop_time": "08:00",
    "retry_interval": 10,
    "max_retry_count": 30,
    "enabled": true
  }'

# 启动抢座 Worker
curl -X POST http://localhost:5000/api/seat/start \
  -H "Authorization: Bearer {token}"

# 查看抢座结果
curl -X GET http://localhost:5000/api/seat/result \
  -H "Authorization: Bearer {token}"
```

### 7.2 Shell 直接调用示例

```bash
# 添加配置
bash shell/seat/seat_config.sh 1 "4F" "4F-A161" 1 "2026-06-08" \
  "07:30" "22:00" "07:00" "08:00" 10 30 15 1 \
  '[{"start_time":"07:30","end_time":"09:30"}]'

# 查看配置
bash shell/seat/list_configs.sh 1

# 手动预约
bash shell/seat/reserve_seat.sh 1 "4F-A161" "2026-06-08" \
  "07:30" "22:00" '[{"start_time":"07:30","end_time":"22:00"}]'

# 启动 Worker
bash shell/seat/start_worker.sh 1

# 查看 Worker 状态
bash shell/seat/worker_status.sh 1

# 停止 Worker
bash shell/seat/stop_worker.sh 1
```

## 8. 注意事项

### 8.1 时间相关

1. **时区**: 所有时间使用服务器本地时区
2. **日期格式**: 
   - 数据库存储：`YYYY-MM-DD`
   - 图书馆 API：`yyyyMMdd`（如 `20260608`）
3. **时间格式**:
   - 配置存储：`HH:mm`
   - 图书馆 API：`YYYY-MM-DD HH:mm:ss`

### 8.2 并发和锁

- Worker 使用 PID 文件防止重复启动
- 文件位置：`runtime/users/{user_id}/seat_worker.pid`
- 同一用户只能运行一个 Worker
- 不同用户可以同时运行各自的 Worker

### 8.3 日志和通知

- 所有操作记录到 `logs` 表
- 抢座结果记录到 `seat_results` 表
- 成功/失败可触发邮件或桌面通知（需配置 `notification_settings`）

### 8.4 错误处理

- 网络错误：自动重试（根据 `retry_interval`）
- 登录失效：需要重新获取 token
- 座位已被预约：尝试下一个候选座位
- 超过最大重试次数：记录失败并退出

## 9. 后续工作

1. **实现图书馆 token 获取逻辑**（Selenium 或 requests）
2. **实现真实 API 调用**（预约、查询、取消）
3. **测试完整流程**（配置 → 启动 Worker → 抢座成功）
4. **添加通知功能**（抢座成功/失败邮件通知）
5. **前端页面开发**（座位配置界面、结果展示）

## 10. Git 提交建议

```bash
git add shell/seat/
git commit -m "feat(shell): implement seat reservation module framework

- Created all seat management shell scripts (config, worker, status)
- Implemented seat_client.py with HAR-analyzed API structure
- Database operations fully working (configs, results, logs)
- Worker management (start/stop/status) completed
- TODO: Implement library token acquisition and real API calls"
```
