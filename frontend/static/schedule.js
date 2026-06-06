import { request, checkLogin } from "./main.js"

window.onload = async () => {
    if (!checkLogin()) return

    await loadTodaySchedule()

    document.getElementById("syncScheduleBtn")?.addEventListener("click", syncSchedule)
    document.getElementById("syncExamBtn")?.addEventListener("click", syncExam)
    document.getElementById("detectChangesBtn")?.addEventListener("click", detectChanges)
}

function setStatus(message, type = "info") {
    const status = document.getElementById("scheduleStatus")
    if (!status) return
    status.className = `alert alert-${type} mb-3`
    status.textContent = message
}

function clearStatus() {
    const status = document.getElementById("scheduleStatus")
    if (!status) return
    status.className = "alert d-none mb-3"
    status.textContent = ""
}

function setButtonLoading(buttonId, loading, text) {
    const button = document.getElementById(buttonId)
    if (!button) return
    if (loading) {
        button.dataset.originalText = button.textContent
        button.disabled = true
        button.textContent = text
        return
    }
    button.disabled = false
    button.textContent = button.dataset.originalText || button.textContent
}

async function loadTodaySchedule() {
    const data = await request("/schedule/today")
    if (!data) return

    const scheduleContainer = document.getElementById("scheduleList")
    const examContainer = document.getElementById("examList")
    const taskContainer = document.getElementById("taskList")
    const courses = data.schedules || data.courses || []
    const exams = data.exams || []
    const tasks = data.tasks || []
    const currentWeekText = document.getElementById("currentWeekText")
    if (currentWeekText) {
        currentWeekText.textContent = data.current_week ? `当前教学第 ${data.current_week} 周` : ""
    }

    if (scheduleContainer) {
        if (courses.length > 0) {
            scheduleContainer.innerHTML = courses.map(s =>
                `<div class="alert alert-info">${s.course_name} - ${s.weekday || ''} ${s.time_slot || s.section || ''} @ ${s.location || s.classroom || '未知'}</div>`
            ).join('')
        } else {
            scheduleContainer.innerHTML = '<p class="text-muted mb-0">今日暂无课程</p>'
        }
    }

    if (examContainer) {
        if (exams.length > 0) {
            examContainer.innerHTML = exams.map(e =>
                `<div class="alert alert-warning">${e.course_name} - ${e.exam_date || e.exam_time || ''} @ ${e.location || e.exam_location || '未知'}</div>`
            ).join('')
        } else {
            examContainer.innerHTML = '<p class="text-muted mb-0">暂无近期考试</p>'
        }
    }

    if (taskContainer) {
        if (tasks.length > 0) {
            taskContainer.innerHTML = tasks.map(t =>
                `<div class="alert alert-${t.priority === 'high' ? 'danger' : 'secondary'}">${t.title} - 截止：${t.deadline}</div>`
            ).join('')
        } else {
            taskContainer.innerHTML = '<p class="text-muted mb-0">暂无待办任务</p>'
        }
    }
}

async function syncSchedule() {
    clearStatus()
    setStatus("正在同步课表，请稍候...", "info")
    setButtonLoading("syncScheduleBtn", true, "同步中...")
    const data = await request("/schedule/sync", { method: "POST" })
    setButtonLoading("syncScheduleBtn", false)
    if (data !== null) {
        setStatus(data.current_week ? `课表同步完成，当前教学第 ${data.current_week} 周` : "课表同步完成", "success")
        await loadTodaySchedule()
    }
}

async function syncExam() {
    clearStatus()
    setStatus("正在同步考试安排，请稍候...", "info")
    setButtonLoading("syncExamBtn", true, "同步中...")
    const data = await request("/schedule/exam/sync", { method: "POST" })
    setButtonLoading("syncExamBtn", false)
    if (data !== null) {
        setStatus("考试安排同步完成", "success")
        await loadTodaySchedule()
    }
}

async function detectChanges() {
    clearStatus()
    setStatus("正在检测课表变动，请稍候...", "info")
    setButtonLoading("detectChangesBtn", true, "检测中...")
    const data = await request("/schedule/changes/detect", { method: "POST" })
    setButtonLoading("detectChangesBtn", false)
    if (data !== null) {
        setStatus("课表变动检测完成", "success")
    }
}
