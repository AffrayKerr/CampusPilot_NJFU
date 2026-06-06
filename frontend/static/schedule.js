
import { request } from "./main.js"

window.onload = async () => {
    const data = await request("/schedule")
    console.log("课表数据", data)
}