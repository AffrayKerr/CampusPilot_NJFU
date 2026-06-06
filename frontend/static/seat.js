import { request, showSuccess, showErr, checkLogin } from "./main.js"

window.onload = async () => {
    if (!checkLogin()) return
    
    await loadSeatConfigs()
    await loadSeatStatus()
    setInterval(loadSeatStatus, 15000)
    
    document.getElementById("addConfigBtn")?.addEventListener("click", addSeatConfig)
    document.getElementById("startWorkerBtn")?.addEventListener("click", startWorker)
    document.getElementById("stopWorkerBtn")?.addEventListener("click", stopWorker)
}

async function loadSeatConfigs() {
    const data = await request("/seat/config/list")
    const configs = Array.isArray(data) ? data : data?.configs

    const tbody = document.querySelector("#configTable tbody")
    if (!tbody) return

    if (!configs) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">暂无座位配置</td></tr>'
        return
    }

    if (configs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">暂无座位配置</td></tr>'
        return
    }

    tbody.innerHTML = configs.map(c => `
        <tr>
            <td>${c.floor || '-'} / ${c.seat_no}</td>
            <td>${c.reserve_date}</td>
            <td>${c.reserve_start_time || '-'} ~ ${c.reserve_end_time || '-'}</td>
            <td>${c.enabled ? '<span class="badge bg-success">启用</span>' : '<span class="badge bg-secondary">禁用</span>'}</td>
            <td>${c.priority}</td>
            <td>
                <button class="btn btn-sm btn-danger" onclick="deleteSeatConfig(${c.id})">删除</button>
            </td>
        </tr>
    `).join('')
}

function setWorkerStatus(running, message = "") {
    const statusEl = document.getElementById("workerStatus")
    if (statusEl) {
        statusEl.textContent = running ? "运行中" : "已停止"
        statusEl.className = running ? "badge bg-success" : "badge bg-secondary"
    }

    const messageEl = document.getElementById("seatWorkerMessage")
    if (!messageEl) return
    if (!message) {
        messageEl.className = "alert alert-info d-none"
        messageEl.textContent = ""
        return
    }
    messageEl.className = running ? "alert alert-info" : "alert alert-warning"
    messageEl.textContent = message
}

async function loadSeatStatus() {
    const data = await request("/seat/status")
    if (!data) return

    const message = data.last_message ? formatWorkerMessage(data.last_message) : ""
    setWorkerStatus(Boolean(data.running), message)
}

function formatWorkerMessage(raw) {
    try {
        const parsed = JSON.parse(raw)
        const message = parsed.message || parsed.status || ""
        if (message.includes("script timeout")) {
            return "最近一次运行结果：获取图书馆登录信息超时，请确认 WebVPN/图书馆页面已登录成功后重试。"
        }
        if (message.includes("library token/appAccNo not found")) {
            return "最近一次运行结果：未获取到图书馆 token，请重新完成 WebVPN 图书馆登录。"
        }
        if (message.includes("chrome profile not found")) {
            return "最近一次运行结果：未找到浏览器登录配置，请先完成 WebVPN 交互登录。"
        }
        if (parsed.message) return `最近一次运行结果：${parsed.message}`
        if (parsed.status) return `最近一次运行状态：${parsed.status}`
    } catch (e) {
        // keep raw text below
    }
    return `最近一次运行信息：${raw}`
}

async function addSeatConfig() {
    const floor = document.getElementById("seatFloor")?.value.trim() || ""
    const seatNo = document.getElementById("seatNo")?.value.trim()
    const reserveDate = document.getElementById("reserveDate")?.value
    const startTime = document.getElementById("startTime")?.value
    const endTime = document.getElementById("endTime")?.value
    const checkStart = document.getElementById("checkStart")?.value || "07:00"
    const checkStop = document.getElementById("checkStop")?.value || "08:10"
    const priority = parseInt(document.getElementById("priority")?.value || "1")

    if (!seatNo || !reserveDate || !startTime || !endTime) {
        showErr("请填写完整的座位配置信息")
        return
    }

    const result = await request("/seat/config", {
        method: "POST",
        body: JSON.stringify({
            floor,
            seat_no: seatNo,
            reserve_date: reserveDate,
            reserve_start_time: startTime,
            reserve_end_time: endTime,
            check_start_time: checkStart,
            check_stop_time: checkStop,
            priority,
            retry_interval: 10,
            max_retry_count: 30,
            max_duration_minutes: 15,
            enabled: true
        })
    })

    if (result !== null) {
        showSuccess("座位配置添加成功")
        await loadSeatConfigs()
    }
}

window.deleteSeatConfig = async function(id) {
    if (!confirm("确定删除此座位配置？")) return
    
    const result = await request("/seat/config/delete", {
        method: "POST",
        body: JSON.stringify({ id })
    })

    if (result !== null) {
        showSuccess("座位配置已删除")
        await loadSeatConfigs()
    }
}

async function startWorker() {
    const result = await request("/seat/start", { method: "POST" })
    if (result !== null) {
        setWorkerStatus(true, "抢座 Worker 已启动，正在准备图书馆登录状态或等待检查窗口。")
        showSuccess("抢座Worker已启动")
        setTimeout(loadSeatStatus, 1000)
    }
}

async function stopWorker() {
    const result = await request("/seat/stop", { method: "POST" })
    if (result !== null) {
        setWorkerStatus(false, "抢座 Worker 已停止。")
        showSuccess("抢座Worker已停止")
        await loadSeatStatus()
    }
}
