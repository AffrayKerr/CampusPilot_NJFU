import { request, checkLogin } from "./main.js"

window.onload = async () => {
    if (!checkLogin()) return

    await loadTodaySchedule()
    await loadNextWeekSchedule()

    document.getElementById("syncScheduleBtn")?.addEventListener("click", syncSchedule)
    document.getElementById("syncExamBtn")?.addEventListener("click", syncExam)
    document.getElementById("detectChangesBtn")?.addEventListener("click", detectChanges)
    document.getElementById("refreshNextWeekBtn")?.addEventListener("click", loadNextWeekSchedule)
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

function toDatetimeLocalValue(date) {
    if (!date || Number.isNaN(date.getTime())) return ""
    const pad = value => String(value).padStart(2, "0")
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function parseExamStartTime(examTime) {
    const text = String(examTime || "").replace("T", " ")
    const match = text.match(/(\d{4}-\d{1,2}-\d{1,2})\s+(\d{1,2}:\d{2})/)
    if (!match) return null
    return new Date(`${match[1]}T${match[2]}`)
}

function defaultReminderAt(exam) {
    const examStart = parseExamStartTime(exam.exam_time || exam.exam_date)
    if (!examStart) return ""
    const minutes = exam.reminders?.[0]?.remind_before_minutes ?? 120
    return toDatetimeLocalValue(new Date(examStart.getTime() - minutes * 60 * 1000))
}

function renderExamItem(exam) {
    const examTime = exam.exam_date || exam.exam_time || ""
    const location = exam.location || exam.exam_location || "未知"
    const reminderValue = defaultReminderAt(exam)
    return `<div class="alert alert-warning">
        <div class="fw-semibold">${exam.course_name}</div>
        <div class="small">${examTime} @ ${location}</div>
        <div class="input-group input-group-sm mt-2">
            <span class="input-group-text">提醒时间</span>
            <input type="datetime-local" class="form-control" id="examReminder-${exam.id}" value="${reminderValue}">
            <button class="btn btn-outline-dark" onclick="saveExamReminder(${exam.id})">保存</button>
        </div>
    </div>`
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
            examContainer.innerHTML = exams.map(renderExamItem).join('')
        } else {
            examContainer.innerHTML = '<p class="text-muted mb-0">暂无本月考试</p>'
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

function parseScheduleReminderAt(value) {
    if (!value) return null
    const normalized = String(value).trim().replace(" ", "T")
    const date = new Date(normalized)
    return Number.isNaN(date.getTime()) ? null : date
}

function parseSectionStart(section) {
    const firstSection = String(section || "").match(/\d+/)?.[0]
    const sectionTimes = {
        "1": "08:00", "2": "08:55", "3": "09:55", "4": "10:50",
        "5": "11:45", "6": "12:40", "7": "14:00", "8": "14:55",
        "9": "15:55", "10": "16:50", "11": "18:30", "12": "19:25", "13": "20:20"
    }
    return firstSection ? sectionTimes[firstSection] || "" : ""
}

function nextWeekCourseStart(course, targetWeek, currentWeek) {
    if (!targetWeek || !currentWeek) return null
    const startTime = parseSectionStart(course.section)
    if (!startTime) return null

    const classDate = new Date()
    classDate.setHours(0, 0, 0, 0)
    classDate.setDate(classDate.getDate() + (targetWeek - currentWeek) * 7 + ((course.weekday || 1) - 1))

    const [hours, minutes] = startTime.split(":").map(Number)
    classDate.setHours(hours, minutes, 0, 0)
    return classDate
}

function defaultScheduleReminderAt(course, targetWeek, currentWeek) {
    const existing = parseScheduleReminderAt(course.absolute_reminder?.remind_at)
    if (existing) return toDatetimeLocalValue(existing)

    const classStart = nextWeekCourseStart(course, targetWeek, currentWeek)
    if (!classStart) return ""
    return toDatetimeLocalValue(new Date(classStart.getTime() - 15 * 60 * 1000))
}

function renderCourseItem(course, targetWeek, currentWeek) {
    const reminderValue = defaultScheduleReminderAt(course, targetWeek, currentWeek)
    return `<div class="border rounded p-2 mb-2 bg-light">
        <div class="fw-semibold">${course.course_name || '未命名课程'}</div>
        <div class="small text-muted">${course.section || ''} ${course.classroom ? `@ ${course.classroom}` : ''}</div>
        <div class="small text-muted">${course.teacher || ''} ${course.week_info || ''}</div>
        <div class="input-group input-group-sm mt-2">
            <span class="input-group-text">提醒时间</span>
            <input type="datetime-local" class="form-control" id="scheduleReminder-${course.id}" value="${reminderValue}">
            <button class="btn btn-outline-primary" onclick="saveScheduleReminder(${course.id})">保存</button>
        </div>
    </div>`
}

async function loadNextWeekSchedule() {
    const container = document.getElementById("nextWeekSchedule")
    const nextWeekText = document.getElementById("nextWeekText")
    if (container) {
        container.innerHTML = '<p class="text-muted mb-0">加载中...</p>'
    }

    const data = await request("/schedule/next-week")
    if (!data || !container) return

    if (nextWeekText) {
        nextWeekText.textContent = data.target_week ? `教学第 ${data.target_week} 周` : "当前教学周未知"
    }

    const weekdays = data.weekdays || []
    const hasCourses = weekdays.some(day => (day.courses || []).length > 0)
    if (!hasCourses) {
        container.innerHTML = '<p class="text-muted mb-0">下周暂无课程</p>'
        return
    }

    container.innerHTML = weekdays.map(day => {
        const courses = day.courses || []
        return `<div class="col-md-6 col-lg-4">
            <div class="border rounded h-100 p-3 bg-white">
                <div class="fw-bold mb-2">${day.weekday_name || `周${day.weekday || ''}`}</div>
                ${courses.length ? courses.map(course => renderCourseItem(course, data.target_week, data.current_week)).join('') : '<p class="text-muted small mb-0">暂无课程</p>'}
            </div>
        </div>`
    }).join('')
}

window.saveScheduleReminder = async function(scheduleId) {
    const input = document.getElementById(`scheduleReminder-${scheduleId}`)
    const remindAt = input?.value
    if (!remindAt) {
        setStatus("请选择课程提醒时间", "warning")
        return
    }

    const result = await request("/reminder/schedule/set-absolute", {
        method: "POST",
        body: JSON.stringify({ schedule_id: scheduleId, remind_at: remindAt })
    })

    if (result !== null) {
        setStatus("课程提醒时间已保存", "success")
        await loadNextWeekSchedule()
    }
}

window.saveExamReminder = async function(examId) {
    const input = document.getElementById(`examReminder-${examId}`)
    const remindAt = input?.value
    if (!remindAt) {
        setStatus("请选择考试提醒时间", "warning")
        return
    }

    const result = await request("/reminder/exam/set-absolute", {
        method: "POST",
        body: JSON.stringify({ exam_id: examId, remind_at: remindAt })
    })

    if (result !== null) {
        setStatus("考试提醒时间已保存", "success")
        await loadTodaySchedule()
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
        await loadNextWeekSchedule()
    }
}

async function syncExam() {
    clearStatus()
    setStatus("正在同步考试安排，请稍候...", "info")
    setButtonLoading("syncExamBtn", true, "同步中...")
    const data = await request("/schedule/exam/sync", { method: "POST" })
    setButtonLoading("syncExamBtn", false)
    if (data !== null) {
        setStatus(`考试安排同步完成，共 ${data.count ?? 0} 门考试`, "success")
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
