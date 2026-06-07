import { request, showSuccess, showErr, checkLogin } from "./main.js"

let savedSeatConfigs = []
let originalEditConfig = null
let detailModal = null
let editModal = null

window.onload = async () => {
    if (!checkLogin()) return
    initSeatConfigModals()
    await loadSeatConfigs()
    await loadSeatStatus()
    setInterval(loadSeatStatus, 15000)
    document.getElementById("addConfigBtn")?.addEventListener("click", addSeatConfig)
    document.getElementById("startWorkerBtn")?.addEventListener("click", startWorker)
    document.getElementById("reserveNowBtn")?.addEventListener("click", reserveNow)
    document.getElementById("stopWorkerBtn")?.addEventListener("click", stopWorker)
    document.getElementById("saveEditConfigBtn")?.addEventListener("click", saveSeatConfigEdit)
    document.getElementById("resetEditConfigBtn")?.addEventListener("click", resetSeatConfigEdit)
}

function initSeatConfigModals() {
    if (!window.bootstrap?.Modal) return
    const detailEl = document.getElementById("seatConfigDetailModal")
    const editEl = document.getElementById("seatConfigEditModal")
    detailModal = detailEl ? new window.bootstrap.Modal(detailEl) : null
    editModal = editEl ? new window.bootstrap.Modal(editEl) : null
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;")
}

function normalizeReserveTimeSlots(config) {
    if (Array.isArray(config.reserve_time_slots) && config.reserve_time_slots.length > 0) return config.reserve_time_slots
    if (config.reserve_start_time || config.reserve_end_time) {
        return [{ start_time: config.reserve_start_time || "", end_time: config.reserve_end_time || "" }]
    }
    return []
}

function formatTimeSlots(config) {
    const slots = normalizeReserveTimeSlots(config)
    if (slots.length > 0) return slots.map(slot => `${escapeHtml(slot.start_time || '-')} ~ ${escapeHtml(slot.end_time || '-')}`).join("<br>")
    return `${escapeHtml(config.reserve_start_time || '-')} ~ ${escapeHtml(config.reserve_end_time || '-')}`
}

function getConfigById(id) {
    return savedSeatConfigs.find(config => Number(config.id) === Number(id)) || null
}

async function loadSeatConfigs() {
    const data = await request("/seat/config/list")
    const configs = Array.isArray(data) ? data : data?.configs
    const tbody = document.querySelector("#configTable tbody")
    if (!tbody) return
    if (!configs || configs.length === 0) {
        savedSeatConfigs = []
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">暂无座位配置</td></tr>'
        return
    }

    savedSeatConfigs = configs.map(config => ({ ...config, reserve_time_slots: normalizeReserveTimeSlots(config) }))
    tbody.innerHTML = savedSeatConfigs.map(c => `
        <tr>
            <td>${escapeHtml(c.floor || '-')} / ${escapeHtml(c.seat_no)}</td>
            <td>${escapeHtml(c.reserve_date || '-')}</td>
            <td>${formatTimeSlots(c)}</td>
            <td>${c.enabled ? '<span class="badge bg-success">启用</span>' : '<span class="badge bg-secondary">禁用</span>'}</td>
            <td>${escapeHtml(c.priority ?? '-')}</td>
            <td>
                <div class="d-flex gap-1 flex-nowrap align-items-center">
                    <button class="btn btn-sm btn-info text-white" onclick="viewSeatConfigDetail(${c.id})">详情</button>
                    <button class="btn btn-sm btn-warning text-dark" onclick="editSeatConfig(${c.id})">编辑</button>
                    <button class="btn btn-sm btn-primary" onclick="reserveSeatConfig(${c.id}, this)">抢</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteSeatConfig(${c.id})">删除</button>
                </div>
            </td>
        </tr>
    `).join("")
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
        if (message.includes("script timeout")) return "最近一次运行结果：获取图书馆登录信息超时，请确认 WebVPN/图书馆页面已登录成功后重试。"
        if (message.includes("library token/appAccNo not found")) return "最近一次运行结果：未获取到图书馆 token，请重新完成 WebVPN 图书馆登录。"
        if (message.includes("chrome profile not found")) return "最近一次运行结果：未找到浏览器登录配置，请先完成 WebVPN 交互登录。"
        if (parsed.message) return `最近一次运行结果：${parsed.message}`
        if (parsed.status) return `最近一次运行状态：${parsed.status}`
    } catch (e) {}
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
    if (!seatNo || !reserveDate || !startTime || !endTime) return showErr("请填写完整的座位配置信息")

    const result = await request("/seat/config", { method: "POST", body: JSON.stringify({ floor, seat_no: seatNo, reserve_date: reserveDate, reserve_start_time: startTime, reserve_end_time: endTime, check_start_time: checkStart, check_stop_time: checkStop, priority, retry_interval: 10, max_retry_count: 30, max_duration_minutes: 15, enabled: true }) })
    if (result !== null) {
        showSuccess("座位配置添加成功")
        await loadSeatConfigs()
    }
}
window.viewSeatConfigDetail = function(id) {
    const config = getConfigById(id)
    if (!config) return showErr("未找到对应的候选座位配置")
    const detailContent = document.getElementById("seatConfigDetailContent")
    if (!detailContent) return
    const slots = normalizeReserveTimeSlots(config)
    const slotHtml = slots.length > 0
        ? slots.map((slot, index) => `<li class="list-group-item d-flex justify-content-between"><span>时间段 ${index + 1}</span><span>${escapeHtml(slot.start_time || '-')} ~ ${escapeHtml(slot.end_time || '-')}</span></li>`).join("")
        : '<li class="list-group-item text-muted">未配置时间段</li>'

    detailContent.innerHTML = `
        <div class="row g-3">
            <div class="col-md-6"><div class="border rounded p-3 h-100">
                <div class="fw-semibold mb-2">基础信息</div>
                <div class="mb-2"><span class="text-muted">楼层：</span>${escapeHtml(config.floor || '-')}</div>
                <div class="mb-2"><span class="text-muted">座位号：</span>${escapeHtml(config.seat_no || '-')}</div>
                <div class="mb-2"><span class="text-muted">预约日期：</span>${escapeHtml(config.reserve_date || '-')}</div>
                <div class="mb-2"><span class="text-muted">优先级：</span>${escapeHtml(config.priority ?? '-')}</div>
                <div><span class="text-muted">状态：</span>${config.enabled ? '<span class="badge bg-success">启用</span>' : '<span class="badge bg-secondary">禁用</span>'}</div>
            </div></div>
            <div class="col-md-6"><div class="border rounded p-3 h-100">
                <div class="fw-semibold mb-2">Worker 参数</div>
                <div class="mb-2"><span class="text-muted">检查窗口：</span>${escapeHtml(config.check_start_time || '-')} ~ ${escapeHtml(config.check_stop_time || '-')}</div>
                <div class="mb-2"><span class="text-muted">重试间隔：</span>${escapeHtml(config.retry_interval ?? '-')} 秒</div>
                <div class="mb-2"><span class="text-muted">最大重试次数：</span>${escapeHtml(config.max_retry_count ?? '-')}</div>
                <div><span class="text-muted">最长运行时长：</span>${escapeHtml(config.max_duration_minutes ?? '-')} 分钟</div>
            </div></div>
            <div class="col-12"><div class="border rounded p-3"><div class="fw-semibold mb-2">预约时间段</div><ul class="list-group">${slotHtml}</ul></div></div>
        </div>`
    detailModal?.show()
}

window.editSeatConfig = function(id) {
    const config = getConfigById(id)
    if (!config) return showErr("未找到对应的候选座位配置")
    originalEditConfig = JSON.parse(JSON.stringify(config))
    fillSeatConfigEditForm(config)
    editModal?.show()
}

function fillSeatConfigEditForm(config) {
    const firstSlot = normalizeReserveTimeSlots(config)[0] || {}
    document.getElementById("editConfigId").value = config.id ?? ""
    document.getElementById("editSeatFloor").value = config.floor || "4F"
    document.getElementById("editSeatNo").value = config.seat_no || ""
    document.getElementById("editReserveDate").value = config.reserve_date || ""
    document.getElementById("editPriority").value = config.priority ?? 1
    document.getElementById("editStartTime").value = config.reserve_start_time || firstSlot.start_time || "07:30"
    document.getElementById("editEndTime").value = config.reserve_end_time || firstSlot.end_time || "22:00"
    document.getElementById("editCheckStart").value = config.check_start_time || "07:00"
    document.getElementById("editCheckStop").value = config.check_stop_time || "08:10"
    document.getElementById("editRetryInterval").value = config.retry_interval ?? 10
    document.getElementById("editMaxRetryCount").value = config.max_retry_count ?? 30
    document.getElementById("editMaxDurationMinutes").value = config.max_duration_minutes ?? 15
    document.getElementById("editEnabled").checked = Boolean(config.enabled)
}

function resetSeatConfigEdit() {
    if (!originalEditConfig) {
        showErr("暂无可恢复的原始配置")
        return
    }
    fillSeatConfigEditForm(originalEditConfig)
}

async function saveSeatConfigEdit() {
    const id = document.getElementById("editConfigId")?.value
    const floor = document.getElementById("editSeatFloor")?.value.trim() || ""
    const seatNo = document.getElementById("editSeatNo")?.value.trim()
    const reserveDate = document.getElementById("editReserveDate")?.value
    const startTime = document.getElementById("editStartTime")?.value
    const endTime = document.getElementById("editEndTime")?.value
    const checkStart = document.getElementById("editCheckStart")?.value || "07:00"
    const checkStop = document.getElementById("editCheckStop")?.value || "08:10"
    const priority = parseInt(document.getElementById("editPriority")?.value || "1")
    const retryInterval = parseInt(document.getElementById("editRetryInterval")?.value || "10")
    const maxRetryCount = parseInt(document.getElementById("editMaxRetryCount")?.value || "30")
    const maxDurationMinutes = parseInt(document.getElementById("editMaxDurationMinutes")?.value || "15")
    const enabled = Boolean(document.getElementById("editEnabled")?.checked)
    if (!id || !seatNo || !reserveDate || !startTime || !endTime) return showErr("请填写完整的编辑信息")

    const saveButton = document.getElementById("saveEditConfigBtn")
    const originalText = saveButton?.textContent || "保存修改"
    if (saveButton) {
        saveButton.disabled = true
        saveButton.textContent = "保存中..."
    }

    try {
        const result = await request("/seat/config/update", { method: "POST", body: JSON.stringify({ id: Number(id), floor, seat_no: seatNo, reserve_date: reserveDate, reserve_start_time: startTime, reserve_end_time: endTime, reserve_time_slots: [{ start_time: startTime, end_time: endTime }], check_start_time: checkStart, check_stop_time: checkStop, priority, retry_interval: retryInterval, max_retry_count: maxRetryCount, max_duration_minutes: maxDurationMinutes, enabled }) })
        if (result !== null) {
            originalEditConfig = null
            editModal?.hide()
            showSuccess("座位配置修改成功")
            await loadSeatConfigs()
        }
    } finally {
        if (saveButton) {
            saveButton.disabled = false
            saveButton.textContent = originalText
        }
    }
}

window.toggleSeatConfigEnabled = async function(id, buttonEl) {
    const config = getConfigById(id)
    if (!config) return showErr("未找到对应的候选座位配置")

    const nextEnabled = !Boolean(config.enabled)
    const originalText = buttonEl?.textContent || "切换"
    if (buttonEl) {
        buttonEl.disabled = true
        buttonEl.textContent = nextEnabled ? "启用中..." : "禁用中..."
    }

    try {
        const firstSlot = normalizeReserveTimeSlots(config)[0] || {}
        const result = await request("/seat/config/update", {
            method: "POST",
            body: JSON.stringify({
                id: Number(config.id),
                floor: config.floor || "",
                seat_no: config.seat_no,
                reserve_date: config.reserve_date || "",
                reserve_start_time: config.reserve_start_time || firstSlot.start_time || "",
                reserve_end_time: config.reserve_end_time || firstSlot.end_time || "",
                reserve_time_slots: normalizeReserveTimeSlots(config),
                check_start_time: config.check_start_time || "07:00",
                check_stop_time: config.check_stop_time || "08:10",
                priority: Number(config.priority || 1),
                retry_interval: Number(config.retry_interval || 10),
                max_retry_count: Number(config.max_retry_count || 30),
                max_duration_minutes: Number(config.max_duration_minutes || 15),
                enabled: nextEnabled
            })
        })

        if (result !== null) {
            showSuccess(`座位配置已${nextEnabled ? '启用' : '禁用'}`)
            await loadSeatConfigs()
        }
    } finally {
        if (buttonEl) {
            buttonEl.disabled = false
            buttonEl.textContent = originalText
        }
    }
}

window.deleteSeatConfig = async function(id) {
    if (!confirm("确定删除此座位配置？")) return
    const result = await request("/seat/config/delete", { method: "POST", body: JSON.stringify({ id }) })
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

function getImmediateReserveConfig() {
    const enabledConfigs = savedSeatConfigs.filter(config => config.enabled).sort((a, b) => (a.priority || 0) - (b.priority || 0))
    return enabledConfigs[0] || savedSeatConfigs[0] || null
}

function getReserveConfigById(id) {
    return savedSeatConfigs.find(config => Number(config.id) === Number(id)) || null
}

async function submitReserve(config, triggerButton = null) {
    if (!config) return showErr("未找到对应的候选座位配置")
    const reserveDate = config.reserve_date || ""
    const startTime = config.reserve_start_time || config.reserve_time_slots?.[0]?.start_time || ""
    const endTime = config.reserve_end_time || config.reserve_time_slots?.[0]?.end_time || ""
    if (!config.seat_no || !reserveDate || !startTime || !endTime) return showErr("所选候选座位配置不完整，请先补全预约日期和时间段")

    const buttonText = triggerButton?.textContent || "抢"
    if (triggerButton) {
        triggerButton.disabled = true
        triggerButton.textContent = "抢座中..."
    }

    try {
        const result = await request("/seat/reserve", { method: "POST", body: JSON.stringify({ floor: config.floor || "", seat_no: config.seat_no, reserve_date: reserveDate, reserve_start_time: startTime, reserve_end_time: endTime, reserve_time_slots: [{ start_time: startTime, end_time: endTime }] }) })
        if (result !== null) {
            const detail = result.message || "提交成功"
            const summary = `${config.floor || '-'} ${config.seat_no} ${reserveDate} ${startTime}-${endTime}`
            showSuccess(`抢座成功：${summary}，${detail}`)
            setWorkerStatus(false, `最近一次立刻抢座结果：${summary}，${detail}`)
            await loadSeatConfigs()
            await loadSeatStatus()
        }
    } finally {
        if (triggerButton) {
            triggerButton.disabled = false
            triggerButton.textContent = buttonText
        }
    }
}

async function reserveNow() {
    const config = getImmediateReserveConfig()
    if (!config) return showErr("请先在候选座位列表中保存至少一条座位配置")
    const btn = document.getElementById("reserveNowBtn")
    await submitReserve(config, btn)
}

window.reserveSeatConfig = async function(id, buttonEl) {
    const config = getReserveConfigById(id)
    await submitReserve(config, buttonEl || null)
}

async function stopWorker() {
    const result = await request("/seat/stop", { method: "POST" })
    if (result !== null) {
        setWorkerStatus(false, "抢座 Worker 已停止。")
        showSuccess("抢座Worker已停止")
        await loadSeatStatus()
    }
}
