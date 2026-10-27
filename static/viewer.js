// Photo + segmentation viewer shared by the Current Sample page and the demo on the home page.
// Markup: #viewerStage with #imageCanvas, #overlayCanvas{Asphalt,Aggregate,Background}, #loupe,
// #bgProcessingLoader/#viewerBusyText, toggles #{red,aggregate,background}OverlayCheckbox,
// #opacitySlider/#opacityValue and #imageType.
import base64toBlob from "./utils.js"

const $ = (id) => document.getElementById(id)

function hexToRgb(hex) {
    hex = hex.replace("#", "")
    if (hex.length === 3) hex = [...hex].map((c) => c + c).join("")
    return [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16))
}

function loadImage(url) {
    return new Promise((resolve, reject) => {
        const img = new Image()
        img.onload = () => resolve(img)
        img.onerror = reject
        img.src = url
    })
}

function pngUrl(base64) {
    return URL.createObjectURL(base64toBlob(base64, "image/png"))
}

// AI / expert result (asphalt_percent, class, class_word) into a value and a class element
export function showResult(element, classElement, result, classLabel, noSampleLabel = "") {
    if (result && result.sample_found === false) {
        // the model found no sample in the photo - no percentage that would look like a result
        element.textContent = "–"
        classElement.textContent = noSampleLabel
        return
    }
    if (!result || result.asphalt_percent === null || result.asphalt_percent === undefined) {
        element.textContent = "–"
        classElement.textContent = ""
        return
    }
    element.textContent = result.asphalt_percent.toFixed(1) + " %"
    classElement.textContent = result.class
        ? classLabel + " " + result.class + (result.class_word ? " · " + result.class_word : "")
        : ""
}

export function createViewer({ onEvaluateShortcut } = {}) {
    // mask colours come from CSS (shared with the PDF report)
    const rootStyles = getComputedStyle(document.documentElement)
    const layers = {
        asphalt: { canvas: $("overlayCanvasAsphalt"), toggle: $("redOverlayCheckbox"), color: rootStyles.getPropertyValue("--mask-bitumen").trim() },
        aggregate: { canvas: $("overlayCanvasAggregate"), toggle: $("aggregateOverlayCheckbox"), color: rootStyles.getPropertyValue("--mask-aggregate").trim() },
        background: { canvas: $("overlayCanvasBackground"), toggle: $("backgroundOverlayCheckbox"), color: rootStyles.getPropertyValue("--mask-background").trim() },
    }
    const imageUrls = { original: null, bw: null }
    const state = { hasImage: false, hasMasks: false, busy: false }

    function setImages(colorBase64, grayBase64) {
        for (const key of Object.keys(imageUrls)) if (imageUrls[key]) URL.revokeObjectURL(imageUrls[key])
        imageUrls.original = pngUrl(colorBase64)
        imageUrls.bw = grayBase64 ? pngUrl(grayBase64) : imageUrls.original
    }

    async function drawPhoto() {
        const url = imageUrls[$("imageType").value] || imageUrls.original
        if (!url) return
        const img = await loadImage(url)
        const canvas = $("imageCanvas")
        canvas.width = img.naturalWidth
        canvas.height = img.naturalHeight
        canvas.getContext("2d").drawImage(img, 0, 0)
        state.hasImage = true
    }

    // masks come as transparent PNGs - paint the opaque pixels in the layer colour
    async function drawMask(layer, base64) {
        const url = pngUrl(base64)
        const img = await loadImage(url)
        URL.revokeObjectURL(url)
        const canvas = layer.canvas
        canvas.width = img.naturalWidth
        canvas.height = img.naturalHeight
        const ctx = canvas.getContext("2d", { willReadFrequently: true })
        ctx.drawImage(img, 0, 0)
        const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height)
        const [r, g, b] = hexToRgb(layer.color)
        const data = pixels.data
        for (let i = 0; i < data.length; i += 4) {
            if (data[i + 3] > 127) {
                data[i] = r
                data[i + 1] = g
                data[i + 2] = b
                data[i + 3] = 255
            } else {
                data[i + 3] = 0
            }
        }
        ctx.putImageData(pixels, 0, 0)
    }

    function opacity() {
        return Number($("opacitySlider").value) / 100
    }

    function applyLayerVisibility() {
        for (const layer of Object.values(layers)) {
            layer.canvas.hidden = !(state.hasMasks && layer.toggle.checked)
            layer.canvas.style.opacity = opacity()
        }
    }

    async function setMasks(data) {
        await Promise.all([
            drawMask(layers.asphalt, data.asphalt_mask),
            drawMask(layers.aggregate, data.aggregate_mask),
            drawMask(layers.background, data.background_mask),
        ])
        state.hasMasks = true
        applyLayerVisibility()
    }

    function clearMasks() {
        state.hasMasks = false
        applyLayerVisibility()
    }

    function setBusy(text) {
        state.busy = Boolean(text)
        $("bgProcessingLoader").hidden = !text
        if (text) $("viewerBusyText").textContent = text
    }

    // magnifying loupe that follows the cursor and shows the photo together with the visible masks
    const stage = $("viewerStage")
    const loupe = $("loupe")
    const ZOOM = 3
    stage.addEventListener("mousemove", (event) => {
        const photo = $("imageCanvas")
        if (!state.hasImage || state.busy) return
        const rect = photo.getBoundingClientRect()
        const x = event.clientX - rect.left
        const y = event.clientY - rect.top
        if (x < 0 || y < 0 || x > rect.width || y > rect.height) {
            loupe.hidden = true
            return
        }
        const ctx = loupe.getContext("2d")
        const scale = photo.width / rect.width
        const size = loupe.width
        const region = (size / ZOOM) * scale
        const sx = x * scale - region / 2
        const sy = y * scale - region / 2
        ctx.clearRect(0, 0, size, size)
        ctx.globalAlpha = 1
        ctx.drawImage(photo, sx, sy, region, region, 0, 0, size, size)
        for (const layer of Object.values(layers)) {
            if (!layer.canvas.hidden) {
                ctx.globalAlpha = opacity()
                ctx.drawImage(layer.canvas, sx, sy, region, region, 0, 0, size, size)
            }
        }
        const half = loupe.offsetWidth / 2
        loupe.style.left = x - half + "px"
        loupe.style.top = y - half + "px"
        loupe.hidden = false
    })
    stage.addEventListener("mouseleave", () => (loupe.hidden = true))

    // controls
    for (const layer of Object.values(layers)) layer.toggle.addEventListener("change", applyLayerVisibility)
    $("opacitySlider").addEventListener("input", () => {
        $("opacityValue").textContent = $("opacitySlider").value + " %"
        applyLayerVisibility()
    })
    $("imageType").addEventListener("change", drawPhoto)

    // keyboard shortcuts (Shift + A/S/D masks, C image, E evaluate) - not while typing into a field
    document.addEventListener("keydown", (event) => {
        if (!event.shiftKey || !event.key || event.ctrlKey || event.metaKey || event.altKey) return
        if (event.target.closest("input, textarea, select, [contenteditable]")) return
        const key = event.key.toLowerCase()
        const toggle = { a: layers.asphalt.toggle, s: layers.aggregate.toggle, d: layers.background.toggle }[key]
        if (toggle) {
            toggle.checked = !toggle.checked
            applyLayerVisibility()
        } else if (key === "c" && state.hasImage) {
            const select = $("imageType")
            select.selectedIndex = (select.selectedIndex + 1) % select.options.length
            drawPhoto()
        } else if (key === "e" && state.hasImage && onEvaluateShortcut) {
            onEvaluateShortcut()
        }
    })

    return { state, setImages, drawPhoto, setMasks, clearMasks, setBusy }
}
