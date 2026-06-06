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
    document.getElementById("testEmailBtn").onclick = testEmail
    document.getElementById("enableEmail")?.addEventListener("change", saveProfile)
    document.getElementById("enableDesktop")?.addEventListener("change", saveProfile)
}

function toBool(value, defaultValue = false) {
    if (value === undefined || value === null) return defaultValue
    if (typeof value === "boolean") return value
    if (typeof value === "number") return value !== 0
    if (typeof value === "string") return ["1", "true", "yes", "on"].includes(value.toLowerCase())
    return Boolean(value)
}

async function loadProfile() {
    const data = await request("/user/profile")
    if (!data) return
    document.getElementById("email").value = data.email || ""
    document.getElementById("enableEmail").checked = toBool(data.enable_email, false)
    document.getElementById("enableDesktop").checked = toBool(data.enable_desktop, true)
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

async function testEmail() {
    const email = document.getElementById("email").value.trim()
    if (!email) {
        showErr("请先填写邮箱")
        return
    }

    await saveProfile()
    const result = await request("/notification/test", {
        method: "POST",
        body: JSON.stringify({
            channel: "email",
            title: "CampusPilot 测试邮件",
            content: "如果你收到这封邮件，说明平台邮件提醒配置已生效。"
        })
    })

    if (result !== null) {
        const emailResult = result.email || result?.data?.email
        if (emailResult === "success") {
            showSuccess("测试邮件已发送，请检查邮箱")
        } else {
            showErr(`测试邮件发送失败：${emailResult || "请检查 SMTP 配置"}`)
        }
    }
}

async function bindCampus() {
    const campusAccount = document.getElementById("campusAccount").value.trim()
    const campusPassword = document.getElementById("campusPassword").value.trim()

    if (!campusAccount || !campusPassword) {
        showErr("请填写校园网账号和密码")
        return
    }

    const bindResult = await request("/campus/bind", {
        method: "POST",
        body: JSON.stringify({ campus_account: campusAccount, campus_password: campusPassword })
    })
    if (bindResult === null) return

    document.getElementById("campusPassword").value = ""

    const statusEl = document.getElementById("campusStatus")
    if (statusEl) {
        statusEl.textContent = "正在启动浏览器..."
        statusEl.className = "badge bg-info"
    }

    const launchResult = await request("/auth/bind-interactive", { method: "POST" })
    if (launchResult === null) {
        await loadCampusStatus()
        return
    }

    if (statusEl) {
        statusEl.textContent = "等待浏览器登录中..."
        statusEl.className = "badge bg-info"
    }

    await pollInteractiveStatus()
    await loadCampusStatus()
}

async function pollInteractiveStatus() {
    const MAX_ATTEMPTS = 120
    const INTERVAL_MS = 3000
    const statusEl = document.getElementById("campusStatus")

    for (let i = 0; i < MAX_ATTEMPTS; i++) {
        await new Promise(r => setTimeout(r, INTERVAL_MS))

        let raw
        try {
            const token = localStorage.getItem("campuspilot_token")
            const res = await fetch("/api/auth/interactive-status", {
                headers: {
                    "Content-Type": "application/json",
                    ...(token ? { Authorization: `Bearer ${token}` } : {})
                }
            })
            raw = await res.json()
        } catch (e) {
            continue
        }

        const status = raw?.data?.status
        if (statusEl) {
            statusEl.textContent = "等待登录中..."
            statusEl.className = "badge bg-info"
        }

        if (status === "completed") {
            showSuccess("WebVPN 登录成功！")
            return
        }
        if (status === "in_progress") {
            continue
        }
        if (status === "failed" || status === "idle" || status === undefined) {
            if (i >= 10) {
                showErr("WebVPN 登录失败，请重试")
                return
            }
            continue
        }
    }

    showErr("等待超时，请检查浏览器是否完成了登录")
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
