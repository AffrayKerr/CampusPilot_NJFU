
import { request } from "./main.js"

window.onload = async () => {
    const logs = await request("/logs")
    console.log("日志列表", logs)
}