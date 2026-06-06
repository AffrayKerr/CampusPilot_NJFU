import { showErr, showSuccess } from "./main.js"

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

            const data = await requestWithoutToken("/account/register", {
                method: "POST",
                body: JSON.stringify({ username, password, email })
            })

            if (data && data.success) {
                showSuccess("注册成功，请登录")
                document.getElementById("username").value = ""
                document.getElementById("email").value = ""
                document.getElementById("password").value = ""
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
                showSuccess("登录成功")
                setTimeout(() => {
                    window.location.href = "/dashboard"
                }, 1000)
            } else {
                showErr(data?.message || "登录失败")
            }
        }
    }
}