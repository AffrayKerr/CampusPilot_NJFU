import { request, showSuccess, showErr, checkLogin } from "./main.js"

window.onload = async () => {
    if (!checkLogin()) return
    
    await loadTasks()
    
    document.getElementById("addTaskBtn")?.addEventListener("click", addTask)
}

async function loadTasks() {
    const data = await request("/schedule/today")
    if (!data || !data.tasks) return

    const tbody = document.querySelector("#taskTable tbody")
    if (!tbody) return

    if (data.tasks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">暂无任务</td></tr>'
        return
    }

    tbody.innerHTML = data.tasks.map(t => `
        <tr>
            <td>${t.title}</td>
            <td>${t.deadline}</td>
            <td><span class="badge bg-${getPriorityColor(t.priority)}">${getPriorityText(t.priority)}</span></td>
            <td>${t.remind_before_minutes ? `提前 ${t.remind_before_minutes} 分钟` : '未设置'}</td>
            <td><span class="badge bg-${getStatusColor(t.status)}">${getStatusText(t.status)}</span></td>
            <td>
                <button class="btn btn-sm btn-success" onclick="markTaskDone(${t.id})">完成</button>
                <button class="btn btn-sm btn-danger" onclick="deleteTask(${t.id})">删除</button>
            </td>
        </tr>
    `).join('')
}

function getPriorityColor(priority) {
    const colors = { high: 'danger', medium: 'warning', low: 'secondary' }
    return colors[priority] || 'secondary'
}

function getPriorityText(priority) {
    const texts = { high: '紧急', medium: '重要', low: '普通' }
    return texts[priority] || priority
}

function getStatusColor(status) {
    const colors = { pending: 'warning', done: 'success', cancelled: 'secondary' }
    return colors[status] || 'secondary'
}

function getStatusText(status) {
    const texts = { pending: '待办', done: '已完成', cancelled: '已取消' }
    return texts[status] || status
}

async function addTask() {
    const title = document.getElementById("taskTitle")?.value.trim()
    const deadline = document.getElementById("taskDeadline")?.value
    const priority = document.getElementById("taskPriority")?.value || "medium"
    const category = document.getElementById("taskCategory")?.value.trim() || ""
    const note = document.getElementById("taskNote")?.value.trim() || ""
    const reminderMinutesRaw = document.getElementById("taskReminderMinutes")?.value.trim() || ""
    const reminderBeforeMinutes = reminderMinutesRaw ? Number(reminderMinutesRaw) : null

    if (!title || !deadline) {
        showErr("请填写任务名称和截止时间")
        return
    }

    if (reminderBeforeMinutes !== null && (!Number.isInteger(reminderBeforeMinutes) || reminderBeforeMinutes <= 0)) {
        showErr("提醒时间必须是大于 0 的整数分钟")
        return
    }

    const result = await request("/schedule/task/add", {
        method: "POST",
        body: JSON.stringify({
            title,
            deadline,
            priority,
            category,
            note,
            repeat_rule: "none",
            remind_before_minutes: reminderBeforeMinutes
        })
    })

    if (result !== null) {
        showSuccess("任务添加成功")
        document.getElementById("taskTitle").value = ""
        document.getElementById("taskDeadline").value = ""
        document.getElementById("taskReminderMinutes").value = ""
        document.getElementById("taskNote").value = ""
        await loadTasks()
    }
}

window.markTaskDone = async function(id) {
    const result = await request("/schedule/task/update", {
        method: "POST",
        body: JSON.stringify({ id, status: "done" })
    })

    if (result !== null) {
        showSuccess("任务已标记为完成")
        await loadTasks()
    }
}

window.deleteTask = async function(id) {
    if (!confirm("确定删除此任务？")) return
    
    const result = await request("/schedule/task/delete", {
        method: "POST",
        body: JSON.stringify({ id })
    })

    if (result !== null) {
        showSuccess("任务已删除")
        await loadTasks()
    }
}
