import { request, showSuccess, showErr } from "./main.js"

window.submitFeedback = async function () {
    const type = document.getElementById("feedbackType")?.value || "other"
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
            title: title || `${getFeedbackTypeText(type)}反馈`,
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
        hideFeedbackDetail()
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
    const feedbacks = Array.isArray(data) ? data : data?.feedbacks
    if (!feedbacks) return

    const container = document.getElementById("myFeedbackList")
    if (!container) return

    if (feedbacks.length === 0) {
        container.innerHTML = '<p class="text-muted">暂无反馈记录</p>'
        return
    }

    container.innerHTML = feedbacks.map(f => `
        <div class="card mb-2 feedback-item" role="button" tabindex="0" data-feedback-id="${f.id}" style="cursor:pointer;">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-start gap-2">
                    <h6 class="mb-2">${escapeHtml(f.title)} <span class="badge bg-${getStatusColor(f.status)}">${getStatusText(f.status)}</span></h6>
                    <small class="text-primary flex-shrink-0">查看详情</small>
                </div>
                <p class="mb-1 text-muted" style="font-size:13px;">${escapeHtml(getSummary(f.content))}</p>
                <small class="text-muted">提交时间：${formatLocalTime(f.created_at)}</small>
                ${f.admin_message ? `<div class="alert alert-info mt-2 mb-0" style="font-size:13px;">管理员回复：${escapeHtml(f.admin_message)}</div>` : ''}
            </div>
        </div>
    `).join('')

    container.querySelectorAll(".feedback-item").forEach(item => {
        item.addEventListener("click", () => showFeedbackDetail(item.dataset.feedbackId))
        item.addEventListener("keydown", event => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault()
                showFeedbackDetail(item.dataset.feedbackId)
            }
        })
    })
}

async function showFeedbackDetail(feedbackId) {
    if (!feedbackId) return

    const detail = await request(`/feedback/${feedbackId}`)
    if (!detail) return

    const container = document.getElementById("feedbackDetail")
    if (!container) return

    container.className = "alert alert-light border mb-3"
    container.innerHTML = `
        <div class="d-flex justify-content-between align-items-start gap-3">
            <div>
                <h5 class="mb-2">${escapeHtml(detail.title)}</h5>
                <div class="mb-2">
                    <span class="badge bg-${getStatusColor(detail.status)}">${getStatusText(detail.status)}</span>
                    <span class="badge bg-secondary ms-1">${getFeedbackTypeText(detail.type)}</span>
                </div>
            </div>
            <button type="button" class="btn-close" id="closeFeedbackDetailBtn" aria-label="关闭"></button>
        </div>
        <div class="small text-muted mb-2">提交时间：${formatLocalTime(detail.created_at)}</div>
        ${detail.updated_at ? `<div class="small text-muted mb-2">更新时间：${formatLocalTime(detail.updated_at)}</div>` : ''}
        ${detail.contact_email ? `<div class="small text-muted mb-2">联系邮箱：${escapeHtml(detail.contact_email)}</div>` : ''}
        <div class="border rounded p-3 bg-white mb-2" style="white-space:pre-wrap;">${escapeHtml(detail.content)}</div>
        ${detail.admin_message ? `<div class="alert alert-info mb-0">管理员回复：${escapeHtml(detail.admin_message)}</div>` : ''}
    `

    document.getElementById("closeFeedbackDetailBtn")?.addEventListener("click", hideFeedbackDetail)
    container.scrollIntoView({ behavior: "smooth", block: "nearest" })
}

function hideFeedbackDetail() {
    const container = document.getElementById("feedbackDetail")
    if (!container) return
    container.className = "alert alert-light border d-none mb-3"
    container.innerHTML = ""
}

function getSummary(content) {
    const text = content || ""
    return text.length > 60 ? `${text.slice(0, 60)}...` : text
}

function formatLocalTime(value) {
    if (!value) return "-"
    const raw = String(value).trim()
    const normalized = raw.includes("T") ? raw : raw.replace(" ", "T")
    const hasTimezone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(normalized)
    const date = new Date(hasTimezone ? normalized : `${normalized}Z`)

    if (Number.isNaN(date.getTime())) return raw

    return date.toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
    })
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;")
}

function getFeedbackTypeText(type) {
    const texts = {
        login: "登录问题",
        schedule: "课表问题",
        seat: "抢座问题",
        notification: "通知问题",
        frontend: "前端问题",
        task: "任务问题",
        ui: "界面优化",
        feature: "功能建议",
        bug: "Bug反馈",
        other: "其他",
    }
    return texts[type] || type || "其他"
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

