import { showErr } from "./main.js"

const baseUrl = "/api"

async function requestWithoutToken(url, opts = {}) {
    try {
        const res = await fetch(baseUrl + url, {
            headers: { "Content-Type": "application/json" },
            ...opts
        })
        const data = await res.json()
        return data
    } catch (e) {
        showErr("网络请求失败：" + e.message)
        return null
    }
}

window.onload = () => {
    const loginBtn = document.getElementById("loginBtn")
    const registerBtn = document.getElementById("registerBtn")

    if (registerBtn) {
        registerBtn.onclick = async () => {
            const username = document.getElementById("username").value.trim()
            const email = document.getElementById("email").value.trim()
            const password = document.getElementById("password").value.trim()

            if (!username || !password) {
                showErr("用户名和密码不能为空")
                return
            }

            if (username.length < 3 || username.length > 32) {
                showErr("用户名长度须在 3 ~ 32 位之间")
                return
            }

            if (!/^[a-zA-Z0-9_-]+$/.test(username)) {
                showErr("用户名只能包含字母、数字、下划线 _ 或连字符 -")
                return
            }

            if (password.length < 6) {
                showErr("密码至少需要 6 位")
                return
            }

            const data = await requestWithoutToken("/account/register", {
                method: "POST",
                body: JSON.stringify({ username, password, email })
            })

            if (data && data.success) {
                document.getElementById("username").value = username
                document.getElementById("email").value = ""
                document.getElementById("password").value = ""
                if (typeof switchTab === "function") {
                    switchTab("login")
                }
            } else {
                showErr(data?.message || "注册失败")
            }
        }
    }

    if (loginBtn) {
        loginBtn.onclick = async () => {
            const username = document.getElementById("username").value.trim()
            const password = document.getElementById("password").value.trim()

            if (!username || !password) {
                showErr("用户名和密码不能为空")
                return
            }

            const data = await requestWithoutToken("/account/login", {
                method: "POST",
                body: JSON.stringify({ username, password })
            })

            if (data && data.success) {
                localStorage.setItem("campuspilot_token", data.data.token)
                localStorage.setItem("campuspilot_user", JSON.stringify(data.data.user))
                window.location.href = "/dashboard"
            } else {
                showErr(data?.message || "登录失败")
            }
        }
    }
}
