
import { request, showErr, showSuccess } from "./main.js"

let selectedSeat = []

window.onload = () => {
    // 选座位
    const seats = document.querySelectorAll(".seat.free")
    seats.forEach(item => {
        item.onclick = () => {
            const no = item.dataset.no
            if (item.classList.contains("select")) {
                item.classList.remove("select")
                selectedSeat = selectedSeat.filter(i => i !== no)
            } else {
                item.classList.add("select")
                selectedSeat.push(no)
            }
            document.getElementById("chooseSeat").innerText = selectedSeat.length
                ? selectedSeat.join("、")
                : "暂无"
        }
    })

    // 提交预约
    document.getElementById("submitBtn").onclick = async () => {
        if (selectedSeat.length === 0) {
            showErr("请先选择座位！")
            return
        }
        const date = document.getElementById("bookDate").value
        const time = document.getElementById("bookTime").value

        const res = await request("/seat/book", {
            method: "POST",
            body: JSON.stringify({ seats: selectedSeat, date, time })
        })

        if (res?.code === 200) {
            showSuccess("预约成功！")
        }
    }
}