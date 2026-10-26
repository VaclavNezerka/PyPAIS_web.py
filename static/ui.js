// Small UI helpers shared by all pages (exposed as window.ui):
// toasts instead of alert(), confirmation dialogs instead of confirm(), a busy overlay and dropdown handling.
;(function () {
    const lang = document.documentElement.lang === "cs" ? "cs" : "en"
    const TEXT = {
        cs: { ok: "OK", cancel: "Zrušit", close: "Zavřít" },
        en: { ok: "OK", cancel: "Cancel", close: "Close" },
    }[lang]

    function toastRegion() {
        let region = document.getElementById("toastRegion")
        if (!region) {
            region = document.createElement("div")
            region.id = "toastRegion"
            region.className = "toast-region"
            region.setAttribute("aria-live", "polite")
            document.body.append(region)
        }
        return region
    }

    // type: "info" | "success" | "warning" | "error"
    function toast(message, type = "info", { timeout } = {}) {
        const el = document.createElement("div")
        el.className = "toast toast-" + type
        el.setAttribute("role", type === "error" ? "alert" : "status")
        const text = document.createElement("p")
        text.textContent = message
        const close = document.createElement("button")
        close.type = "button"
        close.className = "toast-close"
        close.setAttribute("aria-label", TEXT.close)
        close.textContent = "×"
        close.addEventListener("click", () => el.remove())
        el.append(text, close)
        toastRegion().append(el)
        const ms = timeout ?? (type === "error" ? 10000 : 5000)
        if (ms > 0) setTimeout(() => el.remove(), ms)
        return el
    }

    function buildDialog({ title, message, buttons }) {
        const dialog = document.createElement("dialog")
        dialog.className = "ui-dialog"
        const form = document.createElement("form")
        form.method = "dialog"
        const body = document.createElement("div")
        body.className = "ui-dialog-body"
        if (title) {
            const h = document.createElement("h2")
            h.textContent = title
            body.append(h)
        }
        const p = document.createElement("p")
        p.textContent = message
        body.append(p)
        const actions = document.createElement("div")
        actions.className = "ui-dialog-actions"
        for (const b of buttons) {
            const btn = document.createElement("button")
            btn.className = "btn " + (b.className || "")
            btn.value = b.value
            btn.textContent = b.label
            actions.append(btn)
        }
        form.append(body, actions)
        dialog.append(form)
        return dialog
    }

    // resolves to true when confirmed
    function confirmDialog(message, { title = "", confirmLabel = TEXT.ok, cancelLabel = TEXT.cancel, danger = false } = {}) {
        return new Promise((resolve) => {
            const dialog = buildDialog({
                title,
                message,
                buttons: [
                    { value: "cancel", label: cancelLabel },
                    { value: "ok", label: confirmLabel, className: danger ? "btn-danger" : "btn-primary" },
                ],
            })
            dialog.addEventListener("close", () => {
                resolve(dialog.returnValue === "ok")
                dialog.remove()
            })
            document.body.append(dialog)
            dialog.showModal()
            dialog.querySelector('button[value="ok"]').focus()
        })
    }

    function alertDialog(message, { title = "", label = TEXT.ok } = {}) {
        return new Promise((resolve) => {
            const dialog = buildDialog({ title, message, buttons: [{ value: "ok", label, className: "btn-primary" }] })
            dialog.addEventListener("close", () => {
                resolve()
                dialog.remove()
            })
            document.body.append(dialog)
            dialog.showModal()
        })
    }

    let busyEl = null
    function busy(show, label = "") {
        if (!show) {
            busyEl?.remove()
            busyEl = null
            return
        }
        if (!busyEl) {
            busyEl = document.createElement("div")
            busyEl.className = "busy-overlay"
            busyEl.setAttribute("role", "status")
            const box = document.createElement("div")
            box.className = "busy-box"
            const spinner = document.createElement("div")
            spinner.className = "spinner spinner-lg"
            box.append(spinner, document.createElement("span"))
            busyEl.append(box)
            document.body.append(busyEl)
        }
        busyEl.querySelector("span").textContent = label
    }

    // dropdowns are <details class="dropdown">: close them on outside click and Escape
    document.addEventListener("click", (event) => {
        document.querySelectorAll("details.dropdown[open]").forEach((d) => {
            if (!d.contains(event.target)) d.removeAttribute("open")
        })
    })
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            document.querySelectorAll("details.dropdown[open]").forEach((d) => d.removeAttribute("open"))
        }
    })

    // links with data-confirm="question" ask before they are followed
    document.addEventListener("click", async (event) => {
        const link = event.target.closest("a[data-confirm]")
        if (!link) return
        event.preventDefault()
        if (await confirmDialog(link.dataset.confirm, { danger: true })) window.location.href = link.href
    })

    // server-side flash messages -> toasts
    document.addEventListener("DOMContentLoaded", () => {
        const categories = { error: "error", danger: "error", success: "success", warning: "warning" }
        document.querySelectorAll("#flashMessages li").forEach((li) => {
            toast(li.textContent.trim(), categories[li.dataset.category] || "info")
        })
    })

    window.ui = { toast, confirmDialog, alertDialog, busy }
})()
