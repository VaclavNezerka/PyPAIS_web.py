// Demo on the home page: guests upload a photo and see the segmentation and the AI assessment.
// Nothing is stored for guests (the photo lives in their session only).
import { createViewer, showResult } from "./viewer.js"

const alerts = await fetch("/translations-alerts").then((response) => response.json())
const ui = window.ui
const $ = (id) => document.getElementById(id)
const viewer = createViewer()

async function runInference() {
    viewer.setBusy(alerts.runningModel)
    try {
        const formData = new FormData()
        formData.append("model_name", $("inference_model").value)
        const response = await fetch("/inference?nocache=" + Date.now(), { method: "POST", body: formData })
        const data = await response.json().catch(() => ({}))
        if (!response.ok || data.status !== "success") throw new Error(data.message || response.statusText)
        await viewer.setMasks(data)
        showResult($("demoAi"), $("demoAiClass"), data, alerts.classLabel, alerts.noSampleFound)
        if (data.sample_found === false) ui.toast(alerts.noSampleFoundHint, "warning")
    } catch (error) {
        ui.toast(alerts.inferenceFailed + " " + (error.message || ""), "error")
    } finally {
        viewer.setBusy(null)
    }
}

async function uploadPhoto(file) {
    if (!file) return
    if (file.type && !file.type.startsWith("image/") && !/\.(heic|heif)$/i.test(file.name)) {
        ui.toast(alerts.notAnImage, "warning")
        return
    }
    $("dropzone").hidden = true
    $("viewer").hidden = false
    viewer.setBusy(alerts.processingPhoto)
    try {
        const formData = new FormData()
        formData.append("file", file)
        const response = await fetch("/process-image?nocache=" + Date.now(), { method: "POST", body: formData })
        if (!response.ok) throw new Error(response.status + " " + response.statusText)
        const data = await response.json()
        viewer.setImages(data.color, data.gray)
        await viewer.drawPhoto()
        viewer.clearMasks()
        showResult($("demoAi"), $("demoAiClass"), null, alerts.classLabel)
    } catch (error) {
        viewer.setBusy(null)
        ui.toast(alerts.uploadFailed + " " + (error.message || ""), "error")
        return
    }
    await runInference()
}

$("fileInput").addEventListener("change", () => {
    const file = $("fileInput").files[0]
    $("fileInput").value = ""
    uploadPhoto(file)
})
$("inference_model").addEventListener("change", () => viewer.state.hasImage && runInference())
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
