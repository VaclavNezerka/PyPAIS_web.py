// Tables with selectable rows (sample records, employees): selection bar, bulk and row actions.
const ui = window.ui
let alerts = {}
const alertsLoaded = fetch("/translations-alerts")
    .then((response) => response.json())
    .then((data) => (alerts = data))

function post(url, data = {}) {
    const body = new FormData()
    for (const [key, value] of Object.entries(data)) body.append(key, value)
    return fetch(url + (url.includes("?") ? "&" : "?") + "nocache=" + Date.now(), { method: "POST", body })
}

// ---------- selection ----------
const table = document.querySelector("table[data-selection-bar]")
const bar = table ? document.getElementById(table.dataset.selectionBar) : null

function rowChecks() {
    return table ? [...table.querySelectorAll("input.row-check")] : []
}

function selected() {
    return rowChecks()
        .filter((box) => box.checked)
        .map((box) => box.value)
}

function updateSelection() {
    const ids = selected()
    for (const box of rowChecks()) box.closest("tr").classList.toggle("is-selected", box.checked)
    if (bar) {
        bar.hidden = ids.length === 0
        bar.querySelector("[data-selection-count]").textContent = ids.length
    }
    const all = table?.querySelector("input.check-all")
    if (all) {
        all.checked = ids.length > 0 && ids.length === rowChecks().length
        all.indeterminate = ids.length > 0 && ids.length < rowChecks().length
    }
}

if (table) {
    table.addEventListener("change", (event) => {
        if (event.target.matches("input.check-all")) {
            for (const box of rowChecks()) box.checked = event.target.checked
        }
        updateSelection()
    })
    updateSelection()
}

// ---------- sample records ----------
async function openSample(id, owned) {
    await alertsLoaded
    if (!owned) {
        const ok = await ui.confirmDialog(alerts.elsesExperiment, { confirmLabel: alerts.confirm, cancelLabel: alerts.cancel })
        if (!ok) return
    }
    const response = await post("/activate-experiment/" + id)
    if (response.ok) window.location.href = "/"
    else ui.toast(alerts.noExperiment, "error")
}

async function exportSelected() {
    await alertsLoaded
    const ids = selected()
    if (ids.length === 1) {
        const ok = await ui.confirmDialog(alerts.exportSingleExperimentNotAllowed + "\n" + alerts.exportSingleExperimentProceeding, {
            confirmLabel: alerts.confirm,
            cancelLabel: alerts.cancel,
        })
        if (!ok) return
    }
    window.location.href = "/export-report/" + ids.join(",")
}

async function deleteSelected() {
    await alertsLoaded
    const ids = selected()
    const ok = await ui.confirmDialog(alerts.sureDeleteExperiments + "\n" + ids.join(", ") + "\n\n" + alerts.cannotBeUndone, {
        confirmLabel: alerts.delete,
        cancelLabel: alerts.cancel,
        danger: true,
    })
    if (!ok) return
    ui.busy(true)
    for (const id of ids) await post("/delete-experiment/" + id)
    window.location.reload()
}

async function newSample() {
    // closes the sample that is open on the Current Sample page (it stays in the records)
    await post("/deactivate-current-experiment")
    window.location.href = "/"
}

// ---------- employees ----------
const EMPLOYEE_ACTIONS = {
    "grant-admin": { url: "/change-admin-privileges", field: "will_be_admin", value: true, message: "grantAdmin" },
    "remove-admin": { url: "/change-admin-privileges", field: "will_be_admin", value: false, message: "removeAdmin" },
    block: { url: "/change-user-blockade", field: "will_be_blocked", value: true, message: "blockUser", danger: true },
    unblock: { url: "/change-user-blockade", field: "will_be_blocked", value: false, message: "unblockUser" },
}

async function employeeAction(name) {
    await alertsLoaded
    const action = EMPLOYEE_ACTIONS[name]
    const usernames = selected()
    if (usernames.length === 0) {
        ui.toast(alerts.noEmployeesSelected, "warning")
        return
    }
    const ok = await ui.confirmDialog(alerts[action.message] + "\n" + usernames.join(", "), {
        confirmLabel: alerts.confirm,
        cancelLabel: alerts.cancel,
        danger: Boolean(action.danger),
    })
    if (!ok) return
    ui.busy(true)
    for (const username of usernames) await post(action.url, { username, [action.field]: action.value })
    window.location.reload()
}

// ---------- wiring ----------
document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]")
    if (!button) return
    const action = button.dataset.action
    if (action === "open") openSample(button.dataset.id, button.dataset.owned !== "false")
    else if (action === "export-selected") exportSelected()
    else if (action === "delete-selected") deleteSelected()
    else if (action === "clear-selection") {
        for (const box of rowChecks()) box.checked = false
        updateSelection()
    } else if (action === "new-sample") newSample()
    else if (action in EMPLOYEE_ACTIONS) employeeAction(action)
})

document.querySelectorAll("select[data-autosubmit]").forEach((select) => {
    select.addEventListener("change", () => select.form.requestSubmit())
})
