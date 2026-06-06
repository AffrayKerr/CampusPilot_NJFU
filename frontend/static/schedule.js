import { request, checkLogin, showSuccess, showErr } from "./main.js"

window.onload = async () => {
    if (!checkLogin()) return
    
    await loadTodaySchedule()
    
    document.getElementById("syncScheduleBtn")?.addEventListener("click", syncSchedule)
    document.getElementById("syncExamBtn")?.addEventListener("click", syncExam)
    document.getElementById("detectChangesBtn")?.addEventListener("click", detectChanges)
}

async function loadTodaySchedule() {
    const data = await request("/schedule/today")
    if (!data) return

    const scheduleContainer = document.getElementById("scheduleList")
    const examContainer = document.getElementById("examList")
    const taskContainer = document.getElementById("taskList")

    if (scheduleContainer && data.schedules && data.schedules.length > 0) {
        scheduleContainer.innerHTML = data.schedules.map(s => 
            `<div class="alert alert-info">${s.course_name} - ${s.weekday} ${s.time_slot} @ ${s.location || '未知'}</div>`
        ).join('')
    }

    if (examContainer && data.exams && data.exams.length > 0) {
        examContainer.innerHTML = data.exams.map(e => 
            `<div class="alert alert-warning">${e.course_name} - ${e.exam_date} @ ${e.location || '未知'}</div>`
        ).join('')
    }

    if (taskContainer && data.tasks && data.tasks.length > 0) {
        taskContainer.innerHTML = data.tasks.map(t => 
            `<div class="alert alert-${t.priority === 'high' ? 'danger' : 'secondary'}">${t.title} - 截止：${t.deadline}</div>`
        ).join('')
    }
}

async function syncSchedule() {
    showSuccess("正在同步课表，请稍候...")
    const data = await request("/schedule/sync", { method: "POST" })
    if (data !== null) {
        showSuccess("课表同步完成")
        await loadTodaySchedule()
    }
}

async function syncExam() {
    showSuccess("正在同步考试安排，请稍候...")
    const data = await request("/schedule/exam/sync", { method: "POST" })
    if (data !== null) {
        showSuccess("考试安排同步完成")
        await loadTodaySchedule()
    }
}

async function detectChanges() {
    showSuccess("正在检测课表变动，请稍候...")
    const data = await request("/schedule/changes/detect", { method: "POST" })
    if (data !== null) {
        showSuccess("课表变动检测完成")
    }
}
