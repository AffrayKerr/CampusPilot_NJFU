import { request, checkLogin, getCurrentUser } from "./main.js"

window.onload = async () => {
    if (!checkLogin()) return

    const user = getCurrentUser()
    if (user) {
        const nameEl = document.getElementById("welcomeUser")
        if (nameEl) nameEl.textContent = user.username
        
        const roleEl = document.getElementById("userRole")
        if (roleEl && user.role === "admin") {
            roleEl.style.display = "inline-block"
        }
    }

    await loadTodaySummary()
    await loadCampusStatus()
}

async function loadTodaySummary() {
    const data = await request("/schedule/today", {}, true)
    if (!data) return

    const courseEl = document.getElementById("todayCourseCount")
    if (courseEl) courseEl.textContent = data.schedules?.length ?? 0

    const taskEl = document.getElementById("todayTaskCount")
    if (taskEl) taskEl.textContent = data.tasks?.length ?? 0

    const examEl = document.getElementById("todayExamCount")
    if (examEl) examEl.textContent = data.exams?.length ?? 0
}

async function loadCampusStatus() {
    const data = await request("/campus/status", {}, true)
    if (!data) return

    const statusEl = document.getElementById("campusBindStatus")
    if (statusEl) {
        if (data.bound) {
            statusEl.textContent = data.session_valid ? "校园网：登录有效" : "校园网：已绑定（未登录）"
            statusEl.className = `badge ${data.session_valid ? "bg-success" : "bg-warning"}`
        } else {
            statusEl.textContent = "校园网：未绑定"
            statusEl.className = "badge bg-secondary"
        }
    }
}
