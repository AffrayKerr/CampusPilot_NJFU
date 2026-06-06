# `NJFU--main` 图书馆抢座系统分析与 CampusPilot_NJFU 改造建议

## 1. 阅读范围

本次主要阅读了 `d:\myself\2\NJFU--main\NJFU--main` 中与校园网 / WebVPN 登录、图书馆 SSO、座位查询和预约有关的代码：

- `src/bot/auth.py`
- `src/bot/core.py`
- `src/bot/network.py`
- `src/bot/seat.py`
- `src/bot/reserve.py`
- `config/settings.py`
- `config/constants.py`
- `scripts/reserve_v8.py`
- `web/bot_runner.py`
- `web/scheduler.py`
- `README.md`

同时对比了当前项目：

- `CampusPilot_NJFU/shell/auth/webvpn_selenium_helper.py`
- `CampusPilot_NJFU/shell/auth/bind_webvpn_interactive.sh`
- `CampusPilot_NJFU/shell/auth/webvpn_client.py`
- `CampusPilot_NJFU/shell/seat/seat_client.py`
- `CampusPilot_NJFU/docs/seat-reservation-module.md`

## 2. `NJFU--main` 的核心结论

`NJFU--main` 的关键思路是：**不要试图只靠纯 requests 完成 WebVPN + 图书馆系统登录，而是先通过真实浏览器完成 WebVPN 和图书馆 SSO，再把浏览器里的 cookie、token、appAccNo 交给 requests 进行后续 API 请求。**

它在 README 中也明确说明：由于 WebVPN 网关校验和跳转较复杂，纯 requests 容易出现无限重定向或资源访问受限，所以核心登录阶段采用浏览器自动化。

## 3. `NJFU--main` 登录流程

### 3.1 使用真实浏览器登录 WebVPN

`src/bot/auth.py` 中的 `AuthManager.browser_login()` 使用 `DrissionPage` 打开：

```text
https://webvpn.njfu.edu.cn
```

如果跳到统一身份认证页面，则自动填写账号密码并提交。

流程摘要：

1. 打开 WebVPN 门户。
2. 如果当前 URL 包含 `authserver`，说明需要 CAS 登录。
3. 查找 `#username`、`#password` 输入框。
4. 输入校园账号和密码。
5. 点击 `#login-submit` 或提交表单。
6. 等待 URL 不再包含 `authserver`。
7. 认为 WebVPN 门户登录完成。

### 3.2 通过 WebVPN 进入图书馆资源系统

登录 WebVPN 后，`NJFU--main` 不直接访问教务系统，而是访问图书馆 SSO 入口：

```text
https://webvpn.njfu.edu.cn/rump_frontend/connect/?target=Library&id=12
```

进入资源跳转页后，如果页面仍在 `rump_frontend`，它会查找 `#url` 链接并点击，继续完成跳转。

### 3.3 点击图书馆页面中的座位预约入口

进入图书馆页面后，它会尝试寻找以下元素：

- `.group-item-img-2`
- `span.group-item-img group-item-img-2`
- 文本 `座位预约`
- 文本 `空间预约`
- href 中包含 `seat` 的链接

点击后，可能会打开新标签页。代码会切换到最新标签页，并等待 SPA 初始化。

### 3.4 提取图书馆 token 和 appAccNo

进入图书馆座位预约 SPA 后，`NJFU--main` 通过浏览器执行同步 XHR 请求：

```text
WEBVPN_BASE + SEAT_PATH + /ic-web/auth/userInfo?vpn-12-libseat.njfu.edu.cn
```

从响应里提取：

- `token`
- `accNo` 或 `appAccNo`

这两个值是后续座位 API 请求的关键。

### 3.5 提取 cookie

`NJFU--main` 同时提取两类 cookie：

1. `page.cookies()` 返回的浏览器 cookie。
2. `document.cookie` 中可见的 cookie。

这样可以避免只保存 Selenium / 浏览器接口返回的部分 cookie，导致后续 requests 请求缺少必要 cookie。

## 4. `NJFU--main` 座位 API 逻辑

### 4.1 基础路径

`config/settings.py` 中定义了图书馆座位系统路径：

```text
https://webvpn.njfu.edu.cn/webvpn/LjIwMS4xNjkuMjE4LjE2OC4xNjc=/LjIwNS4xNTguMjAwLjE3MS4xNTMuMTUwLjIxNi45Ny4yMTEuMTU2LjE1OC4xNzMuMTQ4LjE1NS4xNTUuMjE3LjEwMC4xNTAuMTY1
```

也就是当前项目中的 `LIBRARY_BASE`。

所有图书馆 API 都需要附带查询参数：

```text
vpn-12-libseat.njfu.edu.cn
```

### 4.2 请求头

后续 requests 调用中，关键请求头是：

```text
token: <library token>
Content-Type: application/json;charset=UTF-8
Accept: application/json, text/plain, */*
User-Agent: Chrome UA
```

### 4.3 查询楼层 / 房间

`SeatManager.get_floor_overview()` 调用：

```text
GET /ic-web/seatMenu?vpn-12-libseat.njfu.edu.cn
```

返回楼层、房间、剩余座位数量等信息。

### 4.4 查询座位

`SeatManager.get_seats_by_room()` 调用：

```text
GET /ic-web/reserve?vpn-12-libseat.njfu.edu.cn&roomIds=<room_id>&resvDates=<yyyyMMdd>&sysKind=8
```

响应中主要字段：

- `devId`：预约时使用的座位设备 ID。
- `devName`：座位名称，如 `2F-B094`。
- `devStatus`：座位状态，`0` 表示空闲。

### 4.5 预约座位

`ReserveManager.reserve()` 调用：

```text
POST /ic-web/reserve?vpn-12-libseat.njfu.edu.cn
```

payload 结构：

```json
{
  "sysKind": 8,
  "appAccNo": 78388,
  "memberKind": 1,
  "resvMember": [78388],
  "resvBeginTime": 1764468600000,
  "resvEndTime": 1764520800000,
  "resvDev": [100455346],
  "resvProperty": 0,
  "captcha": "",
  "memo": "",
  "testName": ""
}
```

注意：`NJFU--main` 使用的是**毫秒时间戳**作为 `resvBeginTime` / `resvEndTime`。

当前 `CampusPilot_NJFU/shell/seat/seat_client.py` 使用的是字符串：

```text
YYYY-MM-DD HH:mm:ss
```

这可能需要结合实际接口验证。如果当前项目预约失败或返回参数错误，建议优先改成毫秒时间戳形式。

## 5. 当前 CampusPilot_NJFU 与 NJFU--main 的差异

## 5.1 登录目标不同

当前 `webvpn_selenium_helper.py` 登录成功后主要 warmup 的是教务系统 `JWC_MAIN_URL`。

而 `NJFU--main` 的抢座系统要求登录后进入：

```text
/rump_frontend/connect/?target=Library&id=12
```

并进一步点击图书馆页中的“座位预约 / 空间预约”入口，最终拿到座位系统的 token 和 appAccNo。

**结论：** 当前 WebVPN 登录成功不等价于图书馆座位系统 token 已经准备好。

## 5.2 当前项目已有图书馆 token 获取逻辑，但可以加强

当前 `seat_client.py` 中已有：

- `get_library_token()`
- `_fetch_token_via_browser()`
- `library_token.json` 缓存
- 从 localStorage 获取 token
- 调用 user API 获取 appAccNo

这和 `NJFU--main` 的方向一致。

但差异是：

1. `NJFU--main` 会明确点击图书馆页面里的座位预约入口。
2. 当前项目 `_fetch_token_via_browser()` 主要访问 `LIBRARY_SSO_URL` 后等待 `localStorage.getItem('token')`，没有显式点击座位预约入口。
3. 如果 token 不在第一层图书馆页面写入，而是在座位预约 SPA 打开后才写入，则当前项目可能拿不到 token。

## 5.3 cookie 保存策略不同

当前 `webvpn_selenium_helper.py` 使用 CDP `Network.getAllCookies` 或 `driver.get_cookies()` 获取 cookie。

`NJFU--main` 额外使用：

```javascript
return document.cookie;
```

补充当前页面可见 cookie。

**建议：** 当前项目可以保留 CDP 方案，同时补充当前页面 `document.cookie` 结果，减少 cookie 不完整导致 requests 校验失败的情况。

## 5.4 session_valid 不应被纯 requests 校验过早覆盖

之前已观察到：Selenium 登录成功后，`webvpn_client.py check` 可能马上判定 `session invalid`，并把数据库中的 `session_valid` 改回 `0`。

这与 `NJFU--main` 的 README 判断一致：WebVPN 下纯 requests 很容易误判或受限。

**建议：** 交互式浏览器登录成功后，不要马上用纯 requests 校验 WebVPN 根地址来覆盖状态。应把浏览器登录状态作为准信号，并把图书馆 token 获取结果作为抢座模块的有效性判断依据。

## 6. 对 CampusPilot_NJFU 的改造建议

### 建议 1：区分 WebVPN 登录状态和图书馆座位系统状态

当前 `campus_accounts.session_valid` 主要表示 WebVPN session 是否有效。

建议在逻辑上区分：

1. `webvpn_session_valid`：WebVPN 浏览器登录是否完成。
2. `library_token_valid`：是否成功获取图书馆 token 和 appAccNo。

如果暂时不改数据库结构，也至少在代码语义上区分：

- `/campus/status` 展示 WebVPN 绑定状态。
- `/seat/status` 或座位模块内部检查图书馆 token 状态。

### 建议 2：WebVPN 交互式登录成功后不要立即 requests 校验根地址

已经删除了 `bind_webvpn_interactive.sh` 中登录成功后的二次 `webvpn_client.py check`，这是正确方向。

后续如果需要校验，应改为：

- 使用浏览器打开目标资源确认可访问；或
- 使用图书馆 token 获取成功作为座位模块可用依据；或
- 用 WebVPN 代理后的具体资源 API 检查，而不是只访问 `WEBVPN_BASE`。

### 建议 3：增强 `webvpn_selenium_helper.py` 的 cookie 提取

建议在现有 `extract_cookies()` 中补充：

1. `Network.getAllCookies`
2. `driver.get_cookies()`
3. `document.cookie`

并保留 cookie 的：

- `name`
- `value`
- `domain`
- `path`

当前项目已经保存了 path，比 `NJFU--main` 更完整，可以继续保留。

### 建议 4：在座位 token 获取时参考 NJFU--main 的“点击座位入口”流程

当前 `seat_client.py` 的 `_fetch_token_via_browser()` 建议增强为：

1. 打开 WebVPN 首页。
2. 注入已保存的 WebVPN cookie。
3. 打开 `LIBRARY_SSO_URL`。
4. 如果停留在 `rump_frontend`，点击 `#url`。
5. 查找并点击座位入口元素：
   - `.group-item-img-2`
   - `text:座位预约`
   - `text:空间预约`
   - href 包含 `seat` 的链接
6. 如果打开新标签页，切换到新标签。
7. 等待 SPA 初始化。
8. 从 localStorage 或 `/ic-web/auth/userInfo` / `/ic-web/auth/user` 获取 token 和 appAccNo。

### 建议 5：统一 userInfo 接口

`NJFU--main` 使用：

```text
/ic-web/auth/userInfo
```

当前项目 `_get_app_acc_no_from_browser()` 使用：

```text
/ic-web/auth/user
```

建议两个都尝试：

1. 先试 `/ic-web/auth/userInfo`
2. 再试 `/ic-web/auth/user`

并兼容字段：

- `data.token`
- `data.accNo`
- `data.appAccNo`
- 顶层 `accNo`
- 顶层 `appAccNo`

### 建议 6：座位预约时间参数建议验证并可能改为毫秒时间戳

`NJFU--main` 预约 payload 使用毫秒时间戳：

```python
resvBeginTime = int(begin_time.timestamp() * 1000)
resvEndTime = int(end_time.timestamp() * 1000)
```

当前项目使用字符串：

```python
"resvBeginTime": f"{reserve_date} {start_time}:00"
"resvEndTime": f"{reserve_date} {end_time}:00"
```

如果当前预约接口返回异常，建议优先改为毫秒时间戳，与 `NJFU--main` 一致。

### 建议 7：roomId 映射需要使用真实座位系统数据

`NJFU--main` 的示例 roomId 包括：

- `100455346`
- `100455344`
- `100455350`
- `100455352`
- `100455354`
- `100455356`
- `100455358`
- `100455360`
- `106658017`
- `111488386`
- `111488388`
- `111488396`

当前项目中的 `FLOOR_ROOM_IDS` 是：

```python
{
    "1F": [100500001],
    "2F": [100500002],
    "3F": [100500003],
    "4F": [100500004, 100500005],
    "5F": [100500006],
}
```

这看起来更像占位数据，可能与实际图书馆系统不一致。

建议：

1. 读取 `NJFU--main/get_API/seat_summary.csv` 和 `seat_filtered.jsonl`。
2. 生成当前项目可用的楼层 / 房间 / 座位映射。
3. 替换或补全 `FLOOR_ROOM_IDS`。
4. 前端选座时尽量使用真实 `roomId + devId`，不要只依赖座位名称模糊匹配。

## 7. 推荐改造顺序

### 阶段 1：稳定 WebVPN 状态显示

目标：用户交互式 WebVPN 登录后，前端稳定显示“已绑定（登录有效）”。

建议：

1. 保持当前 Selenium 登录成功后写 `session_valid = 1`。
2. 不要立即用 `webvpn_client.py check` 覆盖状态。
3. `/interactive-status` 以 Selenium 写入的 completed 为准。
4. 前端收到 completed 后刷新 `/campus/status`。

### 阶段 2：稳定图书馆 token 获取

目标：座位模块执行前能稳定拿到 token 和 appAccNo。

建议修改 `seat_client.py`：

1. 参考 `NJFU--main` 的图书馆 SSO 跳转流程。
2. 必要时点击座位预约入口。
3. 同时尝试 `/auth/userInfo` 和 `/auth/user`。
4. 成功后缓存 `library_token.json`。

### 阶段 3：修正座位 API 参数

目标：座位查询与预约接口参数与真实系统一致。

建议：

1. 替换真实 roomId 映射。
2. 验证 `resvBeginTime` / `resvEndTime` 使用字符串还是毫秒时间戳。
3. 如果字符串失败，改为毫秒时间戳。
4. 返回结果中保存 `uuid` 和 `resvId`，方便取消和日志展示。

### 阶段 4：完善任务调度和重试

`NJFU--main` 的调度器逻辑可参考：

- T 日预约 T+1 日座位。
- 根据星期五闭馆时间调整结束时间。
- 线程池限制并发浏览器数量。
- 成功后通知用户。

当前项目已有 worker 和 retry 结构，可以继续保留，只需要增强登录/token/roomId/API 参数。

## 8. 最小可行修改清单

如果只做最小改动，建议按下面顺序：

1. `shell/auth/bind_webvpn_interactive.sh`
   - 保持不执行成功后的 `webvpn_client.py check`。

2. `shell/auth/webvpn_selenium_helper.py`
   - 增强 cookie 提取，补充 `document.cookie`。

3. `shell/seat/seat_client.py`
   - `_fetch_token_via_browser()` 增加点击图书馆“座位预约 / 空间预约”入口逻辑。
   - `_get_app_acc_no_from_browser()` 同时支持 `/auth/userInfo` 和 `/auth/user`。
   - `reserve_seat()` 视接口实际情况改为毫秒时间戳。
   - `FLOOR_ROOM_IDS` 替换为 `NJFU--main/get_API` 中真实 roomId。

4. 前端和数据库暂时不必大改。

## 9. 风险点

1. **自动登录账号密码**：`NJFU--main` 会自动填写统一认证账号密码，当前项目采用用户手动浏览器登录，更安全但交互成本高。
2. **WebVPN 风控**：纯 requests 检查容易误判，不能作为交互式登录成功后的强制覆盖依据。
3. **token 过期**：当前项目 token TTL 是 6 小时，应在抢座前确认 token 仍可用，失败时自动重新打开浏览器获取。
4. **roomId / devId 变化**：座位系统数据可能变动，需要保留动态刷新楼层座位的能力。
5. **并发浏览器**：如果多个用户同时抢座，应限制并发 Chrome 数量，避免系统资源耗尽。

## 10. 总结

`NJFU--main` 最值得借鉴的不是具体 Web 框架，而是认证策略：

> 用真实浏览器完成 WebVPN 和图书馆 SSO，提取 token、appAccNo 和 cookie，再用 requests 调用座位 API。

当前 `CampusPilot_NJFU` 已经有相似框架，但需要重点修正：

1. 不要让纯 requests 的 WebVPN 根地址校验覆盖 Selenium 登录成功状态。
2. 图书馆 token 获取流程要更贴近真实页面：进入 Library SSO 后点击座位预约入口。
3. 真实 roomId 映射和预约时间格式需要参考 `NJFU--main` 校准。

建议下一步优先修改 `shell/seat/seat_client.py` 的 token 获取流程，而不是继续改 WebVPN 登录显示逻辑。
