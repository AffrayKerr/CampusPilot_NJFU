
import { request } from "./main.js"

window.onload = async () => {
    const data = await request("/dashboard")
    console.log("首页数据", data)
}