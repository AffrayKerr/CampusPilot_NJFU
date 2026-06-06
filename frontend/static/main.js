
export const baseUrl = "/api"

export function showSuccess(msg) {
    alert("成功：" + msg)
}

export function showErr(msg) {
    alert("错误：" + msg)
}

export async function request(url, opts = {}, silent = false) {
    try {
        const token = localStorage.getItem("campuspilot_token")
        const { silent: _ignored, ...fetchOpts } = opts

        const res = await fetch(baseUrl + url, {
            headers: {
                "Content-Type": "application/json",
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            ...fetchOpts
        })

        const data = await res.json()

        if (!data.success) {
            if (data.message === "Authentication required") {
                localStorage.removeItem("campuspilot_token")
                localStorage.removeItem("campuspilot_user")
                showErr("登录已过期，请重新登录")
                setTimeout(() => { window.location.href = "/" }, 1500)
                return null
            }
            if (!silent) {
                showErr(data.message || "操作失败")
            }
            return null
        }

        return data.data
    } catch (e) {
        if (!silent) {
            showErr("网络请求失败：" + e.message)
        }
        return null
    }
}

export function checkLogin() {
    const token = localStorage.getItem("campuspilot_token")
    if (!token) {
        showErr("请先登录")
        setTimeout(() => {
            window.location.href = "/"
        }, 1500)
        return false
    }
    return true
}

export function getCurrentUser() {
    const userStr = localStorage.getItem("campuspilot_user")
    if (userStr) {
        try {
            return JSON.parse(userStr)
        } catch (e) {
            return null
        }
    }
    return null
}