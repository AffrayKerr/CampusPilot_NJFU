
// 后端接口前缀
export const baseUrl = "/api"

//成功弹窗
export function showSuccess(msg) {
    alert("成功：" + msg)
}
//错误弹窗
export function showErr(msg) {
    alert("错误：" + msg)
}

//通用请求封装
export async function request(url, opts = {}) {
    try {
        const res = await fetch(baseUrl + url, {
            headers: { "Content-Type": "application/json" },
            ...opts
        })
        return await res.json()
    } catch (e) {
        showErr("网络请求失败：" + e.message)
        return null
    }
}