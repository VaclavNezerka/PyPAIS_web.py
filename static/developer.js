/* Developer pages (developer.html, developer_events.html): the tooltips of the charts, the widths of the horizontal
   bars and the filters that apply on change. The CSP allows no inline styles - sizes are set here through the CSSOM.
   Tooltips only repeat what the tables and numbers on the page show. */
"use strict"

document.querySelectorAll(".hbar[data-share]").forEach((bar) => {
    const share = Math.max(0, Math.min(1, Number(bar.dataset.share) || 0))
    bar.style.width = share * 100 + "%"
    bar.hidden = share === 0 // no stub for nothing
})

document.querySelectorAll("[data-autosubmit]").forEach((control) => {
    control.addEventListener("change", () => control.form.requestSubmit())
})

const tooltip = document.createElement("div")
tooltip.className = "chart-tooltip"
tooltip.hidden = true
tooltip.setAttribute("aria-hidden", "true") // screen readers get the aria-label of the mark
document.body.append(tooltip)

const MARKS = ".chart-col, .heat-cell[data-tip], .hbars li"
const numberFormat = new Intl.NumberFormat(document.documentElement.lang || undefined)

function seriesNames(mark) {
    const figure = mark.closest("[data-series]")
    try {
        return figure ? JSON.parse(figure.dataset.series) : []
    } catch {
        return []
    }
}

/** The value leads, the series name follows; texts go in as textContent (names come from the database). */
function showTooltip(mark, x, y) {
    const values = (mark.dataset.values || "").split(",").filter((v) => v !== "")
    const names = seriesNames(mark)
    const title = document.createElement("div")
    title.className = "tip-title"
    title.textContent = mark.dataset.tip || ""
    tooltip.replaceChildren(title)
    values.forEach((value, i) => {
        const row = document.createElement("div")
        row.className = "tip-row"
        if (names.length > 1) {
            const key = document.createElement("i")
            key.className = "tip-key part-" + i
            row.append(key)
        }
        const strong = document.createElement("strong")
        strong.textContent = numberFormat.format(Number(value))
        row.append(strong)
        if (names[i]) {
            const name = document.createElement("span")
            name.textContent = names[i]
            row.append(name)
        }
        tooltip.append(row)
    })
    tooltip.hidden = false
    placeTooltip(x, y)
}

function placeTooltip(x, y) {
    const gap = 12
    const box = tooltip.getBoundingClientRect()
    let left = x + gap
    let top = y - box.height - gap
    if (left + box.width > window.innerWidth - 8) left = Math.max(8, x - box.width - gap)
    if (top < 8) top = y + gap
    tooltip.style.left = left + "px"
    tooltip.style.top = top + "px"
}

document.addEventListener("pointerover", (event) => {
    const mark = event.target.closest(MARKS)
    if (mark) showTooltip(mark, event.clientX, event.clientY)
})
document.addEventListener("pointermove", (event) => {
    if (!tooltip.hidden && event.target.closest(MARKS)) placeTooltip(event.clientX, event.clientY)
})
document.addEventListener("pointerout", (event) => {
    const mark = event.target.closest(MARKS)
    if (mark && !mark.contains(event.relatedTarget)) tooltip.hidden = true
})
document.addEventListener("focusin", (event) => {
    const mark = event.target.closest(MARKS)
    if (!mark) return
    const box = mark.getBoundingClientRect()
    showTooltip(mark, box.left + box.width / 2, box.top)
})
document.addEventListener("focusout", () => {
    tooltip.hidden = true
})
window.addEventListener("scroll", () => {
    tooltip.hidden = true
}, { passive: true })
