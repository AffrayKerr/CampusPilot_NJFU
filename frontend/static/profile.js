import { request, showSuccess, showErr, checkLogin, getCurrentUser } from "./main.js"

window.onload = async () => {
    if (!checkLogin()) return

    const user = getCurrentUser()
    if (user) {
        document.getElementById("username").value = user.username || ""
        document.getElementById("userRole").textContent = user.role === "admin" ? "管理员" : "普通用户"
    }

    await loadProfile()
    await loadCampusStatus()
    await loadStatistics()

    document.getElementById("saveProfileBtn").onclick = saveProfile
    document.getElementById("bindBtn").onclick = bindCampus
    document.getElementById("unbindBtn").onclick = unbindCampus
    document.getElementById("logoutBtn").onclick = logout
}

async function loadProfile() {
    const data = await request("/user/profile")
    if (!data) return
    document.getElementById("email").value = data.email || ""
    document.getElementById("enableEmail").checked = false
    document.getElementById("enableDesktop").checked = true
}

async function loadCampusStatus() {
    const data = await request("/campus/status")
    if (!data) return

    const statusEl = document.getElementById("campusStatus")
    const campusAccountInput = document.getElementById("campusAccount")
    const unbindBtn = document.getElementById("unbindBtn")

    if (data.bound) {
        statusEl.textContent = data.session_valid ? "已绑定（登录有效）" : "已绑定（未登录）"
        statusEl.className = data.session_valid ? "badge bg-success" : "badge bg-warning"
        campusAccountInput.value = data.campus_account || ""
        unbindBtn.style.display = "inline-block"
    } else {
        statusEl.textContent = "未绑定"
        statusEl.className = "badge bg-secondary"
        unbindBtn.style.display = "none"
    }
}

async function loadStatistics() {
    const data = await request("/user/statistics")
    if (!data) return

    document.getElementById("statCourses").textContent = data.schedule?.course_count ?? 0
    document.getElementById("statExams").textContent = data.schedule?.exam_count ?? 0
    document.getElementById("statTasks").textContent = data.tasks?.total ?? 0
    document.getElementById("statSeatSuccess").textContent = data.seat?.success_count ?? 0
}

async function saveProfile() {
    const email = document.getElementById("email").value.trim()
    const enableEmail = document.getElementById("enableEmail").checked
    const enableDesktop = document.getElementById("enableDesktop").checked

    const result = await request("/user/profile", {
        method: "POST",
        body: JSON.stringify({ email, enable_email: enableEmail, enable_desktop: enableDesktop })
    })
    if (result !== null) {
        showSuccess("个人信息保存成功")
        localStorage.setItem("campuspilot_user", JSON.stringify({
            ...getCurrentUser(),
            email
        }))
    }
}

async function bindCampus() {
    const campusAccount = document.getElementById("campusAccount").value.trim()
    const campusPassword = document.getElementById("campusPassword").value.trim()

    if (!campusAccount || !campusPassword) {
        showErr("请填写校园网账号和密码")
        return
    }

    const result = await request("/campus/bind", {
        method: "POST",
        body: JSON.stringify({ campus_account: campusAccount, campus_password: campusPassword })
    })
    if (result !== null) {
        showSuccess("校园网账号绑定成功")
        document.getElementById("campusPassword").value = ""
        await loadCampusStatus()
    }
}

async function unbindCampus() {
    if (!confirm("确定要解绑校园网账号吗？")) return

    const result = await request("/campus/unbind", { method: "POST" })
    if (result !== null) {
        showSuccess("已解绑校园网账号")
        document.getElementById("campusAccount").value = ""
        await loadCampusStatus()
    }
}

async function logout() {
    await request("/account/logout", { method: "POST" })
    localStorage.removeItem("campuspilot_token")
    localStorage.removeItem("campuspilot_user")
    window.location.href = "/"
}
