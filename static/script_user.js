// User profile (default values of the sample form) and the company key page.

// ---------- default values: loaded from the server, autosaved shortly after typing stops ----------
const defaultInputs = document.querySelectorAll(".default-input")
const defaultsStatus = document.getElementById("defaultsStatus")
const defaultsTimers = {}
let defaultsTexts = {}

async function saveDefault(input) {
    defaultsStatus.className = "save-status saving"
    defaultsStatus.textContent = defaultsTexts.saveStatusSaving || "…"
    try {
        const response = await fetch("/update-default-experiment-info", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ field: input.id, value: input.value }),
        })
        if (!response.ok) throw new Error(response.status + " " + response.statusText)
        defaultsStatus.className = "save-status saved"
        defaultsStatus.textContent = (defaultsTexts.saveStatusSaved || "") + " " + new Date().toLocaleTimeString() + " ✓"
    } catch (error) {
        defaultsStatus.className = "save-status error"
        defaultsStatus.textContent = (defaultsTexts.saveStatusError || "") + " " + error.message
    }
}

if (defaultInputs.length) {
    fetch("/translations-alerts")
        .then((response) => response.json())
        .then((data) => (defaultsTexts = data))
    fetch("/get-default-experiment-info")
        .then((response) => response.json())
        .then((data) => {
            for (const [key, value] of Object.entries(data.data || {})) {
                const input = document.getElementById(key)
                if (input && input.classList.contains("default-input") && value !== null) input.value = value
            }
        })
    defaultInputs.forEach((input) => {
        input.addEventListener("input", () => {
            clearTimeout(defaultsTimers[input.id])
            defaultsTimers[input.id] = setTimeout(() => saveDefault(input), 500)
        })
    })
}

// ---------- company key: copy, and hide it after a minute ----------
const companyKey = document.getElementById("companyKey")
if (companyKey) {
    document.getElementById("copyCompanyKey").addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(companyKey.dataset.key)
            window.ui.toast("✓ " + companyKey.dataset.key, "success")
        } catch (error) {
            window.getSelection().selectAllChildren(companyKey)
        }
    })
    setTimeout(() => {
        companyKey.textContent = "•".repeat(companyKey.dataset.key.length)
        document.getElementById("copyCompanyKey").hidden = true
        document.getElementById("keyHideNote").hidden = true
    }, 60000)
}
