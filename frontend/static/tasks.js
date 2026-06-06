
import { request, showSuccess, showErr } from "./main.js"

window.onload = () => {
    const addBtn = document.getElementById("addTask")
    const tbody = document.querySelector("#taskTable tbody")

    //新增任务
    addBtn.onclick = async () => {
        let name = document.getElementById("taskName").value.trim()
        let date = document.getElementById("taskDate").value
        let level = document.getElementById("taskLevel").value
        if (!name || !date) {
            showErr("任务名称和截止日期必填")
            return
        }
        let res = await request("/task/add", {
            method: "POST",
            body: JSON.stringify({ name, date, level })
        })
        if (res?.code === 200) {
            showSuccess("任务添加成功")
            location.reload()
        }
    }

    //删除任务
    tbody.onclick = async e => {
        let tr = e.target.closest("tr")
        let taskName = tr.children[0].innerText
        if (e.target.classList.contains("del")) {
            await request(`/task/del?name=${taskName}`, { method: "DELETE" })
            showSuccess("删除成功")
            tr.remove()
        }
        if (e.target.classList.contains("edit")) {
            alert("修改弹窗，后续对接接口")
        }
    }
}