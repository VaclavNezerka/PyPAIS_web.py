// Current Sample page (workbench): photo upload / camera, segmentation viewer (viewer.js), sample data
// with autosave, assessment and evaluation. The camera itself is handled by script_video.js.
import { createViewer, showResult as renderResult } from "./viewer.js"

const alerts = await fetch("/translations-alerts", { method: "GET" }).then((response) => response.json())
const ui = window.ui
const $ = (id) => document.getElementById(id)

// sample information stored with the experiment (the expert guess is handled separately)
const INFO_FIELDS = [
    "info_sample_label",
    "info_sample_collection_data",
    "info_place_of_experiment",
    "info_test_procedure",
    "info_wrapping_temperature_aggregate",
    "info_wrapping_temperature_binder",
    "info_exposing_water_temperature",
    "info_datetime",
    "info_comment",
    "info_aggregate",
    "info_binder",
]
// fields that describe one particular sample - cleared when a new photo starts a new sample
const PER_SAMPLE_FIELDS = ["info_sample_label", "info_comment", "info_sample_collection_data"]

const viewer = createViewer({ onEvaluateShortcut: () => !state.evaluated && evaluateSample() })
const state = {
    evaluated: false,
    experimentId: null,
}

function showResult(element, classElement, result) {
    renderResult(element, classElement, result, alerts.classLabel)
}

// ---------------------------------------------------------------------------------------------
// Page states, stepper
// ---------------------------------------------------------------------------------------------
function showWorkbench() {
    $("workbench").classList.remove("is-empty")
    $("dropzone").hidden = true
    $("viewer").hidden = false
    $("workbenchPanel").hidden = false
    $("actionBar").hidden = false
}

function setFormEnabled(enabled) {
    for (const id of [...INFO_FIELDS, "expertGuess"]) $(id).disabled = !enabled
    $("save_experiment_info").disabled = !enabled
    $("index_evaluation").disabled = !enabled
}

function updateStepper() {
    const labelFilled = $("info_sample_label").value.trim() !== ""
    const guessFilled = $("expertGuess").value !== ""
    const done = {
        photo: viewer.state.hasImage,
        info: viewer.state.hasImage && labelFilled,
        assess: viewer.state.hasMasks && guessFilled,
        report: state.evaluated,
    }
    let currentSet = false
    for (const step of document.querySelectorAll("#stepper .step")) {
        const isDone = done[step.dataset.step]
        step.classList.toggle("is-done", isDone)
        const isCurrent = !isDone && !currentSet
        step.classList.toggle("is-current", isCurrent)
        if (isCurrent) {
            currentSet = true
            step.setAttribute("aria-current", "step")
        } else {
            step.removeAttribute("aria-current")
        }
    }
    const label = $("info_sample_label").value.trim()
    $("sampleSubtitle").textContent = !viewer.state.hasImage
        ? alerts.subtitleEmpty
        : (state.experimentId ? alerts.sampleId + " " + state.experimentId : "") + (label ? " · " + label : "")
}

// ---------------------------------------------------------------------------------------------
// Saving of the sample data: every change is autosaved shortly after the typing stops, the Save
// button (and the evaluation) store the whole form at once. All saves go through one queue, so they
// reach the server in the order they were made, and the status tells whether the data is stored.
// ---------------------------------------------------------------------------------------------
const AUTOSAVE_DELAY_MS = 500
const autosaveTimers = {}
const unsavedFields = new Set()
let saveQueue = Promise.resolve()
let pendingSaves = 0
let lastSaveError = null
let lastSavedAt = null

function fieldValue(field) {
    if (field === "expert_guess") {
        const value = $("expertGuess").value
        return value === "" ? "" : value / 100
    }
    return $(field).value
}

function refreshSaveStatus() {
    const status = $("saveStatus")
    status.className = "save-status"
    if (pendingSaves > 0) {
        status.classList.add("saving")
        status.textContent = alerts.saveStatusSaving
    } else if (lastSaveError !== null) {
        status.classList.add("error")
        status.textContent = alerts.saveStatusError + " " + lastSaveError
    } else if (unsavedFields.size > 0) {
        status.classList.add("unsaved")
        status.textContent = alerts.saveStatusUnsaved
    } else if (lastSavedAt !== null) {
        status.classList.add("saved")
        status.textContent = alerts.saveStatusSaved + " " + lastSavedAt.toLocaleTimeString() + " ✓"
    } else {
        status.textContent = ""
    }
}

// sends the fields (their values are read when the request is actually sent); resolves to true once stored
function queueSave(url, fields) {
    pendingSaves += 1
    fields.forEach((field) => unsavedFields.delete(field))
    refreshSaveStatus()
    saveQueue = saveQueue.then(async () => {
        const formData = new FormData()
        fields.forEach((field) => formData.append(field, fieldValue(field)))
        try {
            const response = await fetch(url, { method: "POST", body: formData })
            const data = await response.json().catch(() => ({}))
            if (!response.ok || data.status !== "success") {
                throw new Error(data.message || response.status + " " + response.statusText)
            }
            lastSaveError = null
            lastSavedAt = new Date()
            return true
        } catch (error) {
            // keep the fields marked, so the Save button sends them again
            fields.forEach((field) => unsavedFields.add(field))
            lastSaveError = error.message
            return false
        } finally {
            pendingSaves -= 1
            refreshSaveStatus()
        }
    })
    return saveQueue
}

function saveFieldNow(field) {
    clearTimeout(autosaveTimers[field])
    delete autosaveTimers[field]
    return queueSave("/update_value/" + field, [field])
}

function scheduleAutosave(field) {
    unsavedFields.add(field)
    refreshSaveStatus()
    clearTimeout(autosaveTimers[field])
    autosaveTimers[field] = setTimeout(() => saveFieldNow(field), AUTOSAVE_DELAY_MS)
}

function saveSampleData() {
    for (const field of Object.keys(autosaveTimers)) {
        clearTimeout(autosaveTimers[field])
        delete autosaveTimers[field]
    }
    return queueSave("/save-experiment-info", [...INFO_FIELDS, "expert_guess"])
}

async function saveWithFeedback() {
    if (await saveSampleData()) ui.toast(alerts.saveStatusSaved + " " + lastSavedAt.toLocaleTimeString(), "success")
    else ui.toast(alerts.saveStatusError + " " + lastSaveError, "error")
}

// default values from the user's profile; only empty fields are filled unless overwrite is set
async function applyDefaults({ overwrite = false, announce = false } = {}) {
    const response = await fetch("/get-default-experiment-info?nocache=" + Date.now())
    const defaults = (await response.json()).data || {}
    const filled = []
    for (const field of INFO_FIELDS) {
        const value = defaults[field]
        if (value === null || value === undefined || value === "") continue
        const input = $(field)
        if (overwrite || input.value === "") {
            input.value = value
            filled.push(saveFieldNow(field))
        }
    }
    await Promise.all(filled)
    if (announce) ui.toast(filled.length ? alerts.defaultsApplied : alerts.noDefaultsToApply, filled.length ? "success" : "info")
    updateStepper()
}

// ---------------------------------------------------------------------------------------------
// Photo upload, inference, opening a stored sample
// ---------------------------------------------------------------------------------------------
function localNowForInput() {
    const now = new Date()
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset())
    return now.toISOString().slice(0, 16)
}

async function runInference() {
    viewer.setBusy(alerts.runningModel)
    try {
        const formData = new FormData()
        formData.append("model_name", $("inference_model").value)
        const response = await fetch("/inference?nocache=" + Date.now(), { method: "POST", body: formData })
        const data = await response.json().catch(() => ({}))
        if (!response.ok || data.status !== "success") throw new Error(data.message || response.statusText)
        if (data.experimentId) state.experimentId = data.experimentId
        await viewer.setMasks(data)
        showResult($("aiPercent"), $("aiClass"), data)
    } catch (error) {
        ui.toast(alerts.inferenceFailed + " " + (error.message || ""), "error")
    } finally {
        viewer.setBusy(null)
        updateStepper()
    }
}

async function uploadPhoto(file) {
    if (!file) return
    if (file.type && !file.type.startsWith("image/") && !/\.(heic|heif)$/i.test(file.name)) {
        ui.toast(alerts.notAnImage, "warning")
        return
    }
    showWorkbench()
    viewer.setBusy(alerts.processingPhoto)
    try {
        const formData = new FormData()
        formData.append("file", file)
        const response = await fetch("/process-image", { method: "POST", body: formData })
        if (!response.ok) throw new Error(response.status + " " + response.statusText)
        const data = await response.json()
        viewer.setImages(data.color, data.gray)
        await viewer.drawPhoto()
        viewer.clearMasks()
        state.evaluated = false
        showResult($("aiPercent"), $("aiClass"), null)

        const active = await fetch("/is-experiment-active").then((r) => r.json())
        state.experimentId = active.experimentId

        // a new photo starts a new sample: clear what belongs to the previous one, keep the series data
        for (const field of PER_SAMPLE_FIELDS) $(field).value = ""
        $("expertGuess").value = ""
        $("info_datetime").value = localNowForInput()
        setFormEnabled(true)
        await Promise.all([...PER_SAMPLE_FIELDS, "expert_guess", "info_datetime", "inference_model"].map(saveFieldNow))
        await applyDefaults()
    } catch (error) {
        viewer.setBusy(null)
        ui.toast(alerts.uploadFailed + " " + (error.message || ""), "error")
        return
    }
    await runInference()
    $("info_sample_label").focus()
}

function inputDateTime(value) {
    // "2026-10-26 09:47:31" (DB) -> "2026-10-26T09:47" (datetime-local input)
    return value ? String(value).replace(" ", "T").slice(0, 16) : ""
}

async function openSample(id) {
    showWorkbench()
    setFormEnabled(false)
    viewer.setBusy(alerts.loadingSample)
    try {
        const response = await fetch("/load-experiment/" + id + "?nocache=" + Date.now())
        const data = await response.json().catch(() => ({}))
        if (!response.ok || data.status !== "success") throw new Error(data.message || alerts.noExperiment)

        state.experimentId = data.experimentId
        for (const field of INFO_FIELDS) {
            const value = data[field]
            $(field).value = value === null || value === undefined ? "" : field === "info_datetime" ? inputDateTime(value) : value
        }
        $("expertGuess").value =
            data.expert_guess === null || data.expert_guess === undefined ? "" : Math.round(data.expert_guess * 100)
        const model = $("inference_model")
        if (data.inference_model && [...model.options].some((o) => o.value === data.inference_model)) {
            model.value = data.inference_model
        }

        viewer.setImages(data.color, data.gray)
        await viewer.drawPhoto()
        setFormEnabled(true)
        if (data.has_masks) {
            await viewer.setMasks(data)
            showResult($("aiPercent"), $("aiClass"), data)
            viewer.setBusy(null)
        } else {
            await runInference()
        }
    } catch (error) {
        viewer.setBusy(null)
        ui.toast(error.message, "error")
    }
    updateStepper()
}

// ---------------------------------------------------------------------------------------------
// Evaluation
// ---------------------------------------------------------------------------------------------
async function evaluateSample() {
    if ($("expertGuess").value === "") {
        ui.toast(alerts.expertGuessEmpty, "warning")
        $("expertGuess").focus()
        return
    }
    if (!viewer.state.hasMasks) {
        ui.toast(alerts.waitForModel, "warning")
        return
    }
    ui.busy(true, alerts.evaluating)
    try {
        // evaluate only once all the sample data is confirmed stored
        if (!(await saveSampleData())) throw new Error(alerts.saveFailed + " " + lastSaveError)
        const response = await fetch("/evaluate-asphalt?nocache=" + Date.now(), { method: "POST" })
        const data = await response.json().catch(() => ({}))
        if (data.status !== "success") throw new Error(alerts.evaluationFailed + " " + (data.message || ""))

        // the sample is finished - the next visit of this page starts a new one
        await fetch("/deactivate-current-experiment", { method: "POST" })
        state.evaluated = true
        state.experimentId = data.experimentId || state.experimentId
        setFormEnabled(false)
        $("editActions").hidden = true
        $("doneActions").hidden = false
        const exportUrl = "/export-report/" + state.experimentId
        $("doneExport").href = exportUrl
        $("resultExport").href = exportUrl
        updateStepper()

        const label = $("info_sample_label").value.trim()
        $("resultSample").textContent = alerts.sampleId + " " + state.experimentId + (label ? " · " + label : "")
        showResult($("resultAi"), $("resultAiClass"), data)
        showResult($("resultExpert"), $("resultExpertClass"), data.expert)
        showResult($("aiPercent"), $("aiClass"), data)
        $("resultDialog").showModal()
    } catch (error) {
        ui.toast(error.message, "error")
    } finally {
        ui.busy(false)
    }
}

// ---------------------------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------------------------
for (const field of INFO_FIELDS) {
    const input = $(field)
    input.addEventListener("input", () => {
        scheduleAutosave(field)
        updateStepper()
    })
    // leaving the field saves it right away
    input.addEventListener("change", () => {
        if (field in autosaveTimers) saveFieldNow(field)
    })
}
$("expertGuess").addEventListener("input", function () {
    if (this.value !== "") {
        const value = Number(this.value)
        if (value < 0) this.value = 0
        else if (value > 100) this.value = 100
    }
    scheduleAutosave("expert_guess")
    updateStepper()
})
$("inference_model").addEventListener("change", async () => {
    await saveFieldNow("inference_model")
    if (viewer.state.hasImage) await runInference()
})

$("save_experiment_info").addEventListener("click", saveWithFeedback)
$("index_evaluation").addEventListener("click", evaluateSample)
$("applyDefaultsButton").addEventListener("click", () => {
    $("applyDefaultsButton").closest("details").removeAttribute("open")
    applyDefaults({ announce: true })
})
$("resultDialog").addEventListener("click", (event) => {
    if (event.target === $("resultDialog")) $("resultDialog").close()
})
window.addEventListener("beforeunload", (event) => {
    if (unsavedFields.size > 0 || pendingSaves > 0) {
        event.preventDefault()
        event.returnValue = ""
    }
})

// upload: file picker, drag and drop, camera (script_video.js puts the captured photo into #fileInput)
$("fileInput").addEventListener("change", () => {
    const file = $("fileInput").files[0]
    $("fileInput").value = ""
    uploadPhoto(file)
})
$("upload-button-camera").addEventListener("click", () => uploadPhoto($("fileInput").files[0]))
for (const zone of [$("dropzone"), $("viewerStage")]) {
    zone.addEventListener("dragover", (event) => {
        event.preventDefault()
        zone.classList.add("is-dragover")
    })
    zone.addEventListener("dragleave", () => zone.classList.remove("is-dragover"))
    zone.addEventListener("drop", (event) => {
        event.preventDefault()
        zone.classList.remove("is-dragover")
        uploadPhoto(event.dataTransfer.files[0])
    })
}

setFormEnabled(false)
updateStepper()

// continue with the sample that is open for this user (if any)
const active = await fetch("/is-experiment-active").then((response) => response.json())
if (active.active) openSample(active.experimentId)
