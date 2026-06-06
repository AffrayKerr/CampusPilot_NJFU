
import { request, showSuccess, showErr } from "./main.js"

window.onload = () => {
    const saveBtn = document.getElementById("saveBtn")

    saveBtn.onclick = async () => {
        let name = document.getElementById("userName").value.trim()
        let uid = document.getElementById("userId").value.trim()
        let phone = document.getElementById("userPhone").value.trim()
        let mail = document.getElementById("userMail").value.trim()

        if (!name || !uid) {
            showErr("姓名和学号不能为空！")
            return
        }

        const res = await request("/user/update", {
            method: "PUT",
            body: JSON.stringify({ name, uid, phone, mail })
        })

        if (res?.code === 200) {
            showSuccess("个人信息保存成功！")
        }
    }
}