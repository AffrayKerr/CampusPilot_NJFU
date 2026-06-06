import { request, checkLogin } from "./main.js"

window.onload = async () => {
    if (!checkLogin()) return
    
    await loadLogs()
    
    document.getElementById("filterAll")?.addEventListener("click", () => loadLogs())
    document.getElementById("filterError")?.addEventListener("click", () => loadErrorLogs())
}

async function loadLogs() {
    const data = await request("/logs/list?limit=100")
    if (!data || !data.logs) return

    renderLogs(data.logs)
}

async function loadErrorLogs() {
    const data = await request("/logs/error?limit=50")
    if (!data || !data.logs) return

    renderLogs(data.logs)
}

function renderLogs(logs) {
    const tbody = document.querySelector("#logTable tbody")
    if (!tbody) return

    if (logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">暂无日志</td></tr>'
        return
    }

    tbody.innerHTML = logs.map(log => {
        const levelBadge = getLevelBadge(log.level)
        const moduleBadge = getModuleBadge(log.module)
        return `
            <tr>
                <td>${log.created_at || '-'}</td>
                <td>${moduleBadge}</td>
                <td>${levelBadge}</td>
                <td>${log.message || '-'}</td>
            </tr>
        `
    }).join('')
}

function getLevelBadge(level) {
    const badges = {
        'INFO': '<span class="badge bg-success">INFO</span>',
        'WARN': '<span class="badge bg-warning">WARN</span>',
        'ERROR': '<span class="badge bg-danger">ERROR</span>',
        'DEBUG': '<span class="badge bg-secondary">DEBUG</span>'
    }
    return badges[level] || `<span class="badge bg-secondary">${level}</span>`
}

function getModuleBadge(module) {
    const badges = {
        'auth': '<span class="badge bg-primary">登录</span>',
        'schedule': '<span class="badge bg-info">课表</span>',
        'seat': '<span class="badge bg-success">抢座</span>',
        'task': '<span class="badge bg-warning">任务</span>',
        'notification': '<span class="badge bg-secondary">通知</span>'
    }
    return badges[module] || `<span class="badge bg-secondary">${module}</span>`
}
