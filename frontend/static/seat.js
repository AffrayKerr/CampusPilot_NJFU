import { request, showSuccess, showErr, checkLogin } from "./main.js"

window.onload = async () => {
    if (!checkLogin()) return
    
    await loadSeatConfigs()
    await loadSeatStatus()
    
    document.getElementById("addConfigBtn")?.addEventListener("click", addSeatConfig)
    document.getElementById("startWorkerBtn")?.addEventListener("click", startWorker)
    document.getElementById("stopWorkerBtn")?.addEventListener("click", stopWorker)
}

async function loadSeatConfigs() {
    const data = await request("/seat/config/list")
    if (!data || !data.configs) return

    const tbody = document.querySelector("#configTable tbody")
    if (!tbody) return

    if (data.configs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">暂无座位配置</td></tr>'
        return
    }

    tbody.innerHTML = data.configs.map(c => `
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

async function loadSeatStatus() {
    const data = await request("/seat/status")
    if (!data) return

    const statusEl = document.getElementById("workerStatus")
    if (statusEl) {
        statusEl.textContent = data.running ? "运行中" : "已停止"
        statusEl.className = data.running ? "badge bg-success" : "badge bg-secondary"
    }
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
        showSuccess("抢座Worker已启动")
        await loadSeatStatus()
    }
}

async function stopWorker() {
    const result = await request("/seat/stop", { method: "POST" })
    if (result !== null) {
        showSuccess("抢座Worker已停止")
        await loadSeatStatus()
    }
}
