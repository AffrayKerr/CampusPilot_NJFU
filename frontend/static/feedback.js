
import { request, showSuccess, showErr } from "./main.js"

window.submitFeedback = async function () {
    let type = document.getElementById("type").value
    let contact = document.getElementById("contact").value.trim()
    let content = document.getElementById("content").value.trim()

    if (!contact || !content) {
        showErr("联系方式和反馈内容不能为空")
        return
    }

    let res = await request("/feedback/add", {
        method: "POST",
        body: JSON.stringify({ type, contact, content })
    })

    if (res?.code === 200) {
        showSuccess("提交成功！感谢你的反馈，我们会尽快处理。")
        document.getElementById("contact").value = ""
        document.getElementById("content").value = ""
    }
}