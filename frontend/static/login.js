
import { request, showErr, showSuccess } from "./main.js"

window.onload = () => {
    const btn = document.querySelector("button")
    btn.onclick = async () => {
        //获取三个输入框：账号、邮箱、密码
        let account = document.querySelectorAll("input")[0].value.trim()
        let email = document.querySelectorAll("input")[1].value.trim()
        let pwd = document.querySelectorAll("input")[2].value.trim()

        if (!account || !email || !pwd) {
            showErr("校园网账号、邮箱、密码不能为空！")
            return
        }

        //请求登录接口
        let data = await request("/login", {
            method: "POST",
            body: JSON.stringify({ account, email, pwd })
        })

        if (data && data.code === 200) {
            showSuccess("登录成功，跳转首页")
            location.href = "dashboard.html"
        } else {
            showErr(data?.msg || "账号或密码错误")
        }
    }
}