import { request, showSuccess, showErr } from "./main.js"

window.submitFeedback = async function () {
    const type = document.getElementById("feedbackType")?.value || "其他"
    const title = document.getElementById("feedbackTitle")?.value.trim() || ""
    const content = document.getElementById("feedbackContent")?.value.trim()
    const contactEmail = document.getElementById("contactEmail")?.value.trim() || ""

    if (!content) {
        showErr("反馈内容不能为空")
        return
    }

    const result = await request("/feedback/submit", {
        method: "POST",
        body: JSON.stringify({
            type,
            title: title || `${type}反馈`,
            content,
            contact_email: contactEmail,
            priority: "medium"
        })
    })

    if (result !== null) {
        showSuccess("提交成功！感谢你的反馈，我们会尽快处理。")
        document.getElementById("feedbackTitle").value = ""
        document.getElementById("feedbackContent").value = ""
        document.getElementById("contactEmail").value = ""
        
        await loadMyFeedback()
    }
}

window.onload = async () => {
    await loadMyFeedback()
    
    const submitBtn = document.getElementById("submitFeedbackBtn")
    if (submitBtn) {
        submitBtn.addEventListener("click", window.submitFeedback)
    }
}

async function loadMyFeedback() {
    const token = localStorage.getItem("campuspilot_token")
    if (!token) return

    const data = await request("/feedback/list")
    if (!data || !data.feedbacks) return

    const container = document.getElementById("myFeedbackList")
    if (!container) return

    if (data.feedbacks.length === 0) {
        container.innerHTML = '<p class="text-muted">暂无反馈记录</p>'
        return
    }

    container.innerHTML = data.feedbacks.map(f => `
        <div class="card mb-2">
            <div class="card-body">
                <h6>${f.title} <span class="badge bg-${getStatusColor(f.status)}">${getStatusText(f.status)}</span></h6>
                <p class="mb-1 text-muted" style="font-size:13px;">${f.content}</p>
                <small class="text-muted">提交时间：${f.created_at || '-'}</small>
                ${f.admin_message ? `<div class="alert alert-info mt-2 mb-0" style="font-size:13px;">管理员回复：${f.admin_message}</div>` : ''}
            </div>
        </div>
    `).join('')
}

function getStatusColor(status) {
    const colors = {
        'pending': 'secondary',
        'processing': 'warning',
        'resolved': 'success',
        'closed': 'dark'
    }
    return colors[status] || 'secondary'
}

function getStatusText(status) {
    const texts = {
        'pending': '待处理',
        'processing': '处理中',
        'resolved': '已解决',
        'closed': '已关闭'
    }
    return texts[status] || status
}
