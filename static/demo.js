import base64toBlob from "./utils.js"
import { hexToRgba, colorizeMask } from "./utils.js"

const alerts = await fetch("/translations-alerts", { method: "GET" }).then(
    (response) => response.json(),
)

let uploadedImageURL_color = null
let uploadedImageURL_gray = null
let uploadedImageURL_nobg = null

let uploadedImageURL_mask_aggregate = null
let uploadedImageURL_mask_asphalt = null
let uploadedImageURL_mask_bg = null

let uploadedImageURL_redOverlay = null
let uploadedImage = new Image()
let uploadedImageOverlay_asphalt = new Image()
let uploadedImageOverlay_aggregate = new Image()
let uploadedImageOverlay_bg = new Image()

// Access CSS variables for label settings
const rootStyles = getComputedStyle(document.documentElement)

// Theme colors
let aggregateColor = hexToRgba(
    rootStyles.getPropertyValue("--myBlue").trim(),
    1,
)
let backgroundColor = hexToRgba(
    rootStyles.getPropertyValue("--myPaleGreen").trim(),
    1,
)
let bitumenColor = hexToRgba(
    rootStyles.getPropertyValue("--myPaleRed").trim(),
    1,
)

// Highcontrast colors
bitumenColor = "rgba(0, 0, 255, 1)"
aggregateColor = "rgba(255, 0, 0, 1)"
backgroundColor = "rgba(0, 255, 0, 1)"

const labelSettings = {
    background: {
        stroke: backgroundColor,
        fill: backgroundColor,
        strokeWidth: 2,
    },
    aggregate: { stroke: aggregateColor, fill: aggregateColor, strokeWidth: 2 },
    asphalt: { stroke: bitumenColor, fill: bitumenColor, strokeWidth: 2 },
    magnify: 3,
    mask_opacity: 0.5,
}

uploadedImage.onload = function () {
    var canvas = document.getElementById("imageCanvas")
    var ctx = canvas.getContext("2d", { willReadFrequently: true })
    // clear the canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    canvas.width = this.width
    canvas.height = this.height
    ctx.drawImage(this, 0, 0, canvas.width, canvas.height)
    magnify("imageCanvas", labelSettings.magnify)
}

function displayed_mask(canvasId, image, color) {
    var canvas = document.getElementById(canvasId)
    var ctx = canvas.getContext("2d", { willReadFrequently: true })
    // clear the canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    canvas.width = image.width
    canvas.height = image.height
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height)

    // create an array from the string
    let colorArray = color.match(/[\d.]+/g).map(Number)
    const imgArray = ctx.getImageData(0, 0, canvas.width, canvas.height)
    const maskImageData = colorizeMask(imgArray, colorArray)
    // const data = maskImageData.data; // Uint8ClampedArray [r,g,b,a, r,g,b,a, ...]
    createImageBitmap(maskImageData).then((bitmap) => {
        ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    })
    magnify(canvasId, labelSettings.magnify)
}

uploadedImageOverlay_asphalt.onload = function () {
    displayed_mask("overlayCanvasAsphalt", this, labelSettings.asphalt.fill)
}
uploadedImageOverlay_aggregate.onload = function () {
    displayed_mask("overlayCanvasAggregate", this, labelSettings.aggregate.fill)
}
uploadedImageOverlay_bg.onload = function () {
    displayed_mask(
        "overlayCanvasBackground",
        this,
        labelSettings.background.fill,
    )
}

uploadImage.onerror = function () {
    console.error("Failed to load image at URL: " + this.src)
    console.error
}

let displayAsphaltMask = true
let displayAggregateMask = true
let displayBackgroundMask = false

disableControls() // Disable controls on page load

function enableControls() {
    // Find all sliders and input boxes and enable them
    document.querySelectorAll(".slider-group input").forEach((input) => {
        input.disabled = false
    })
}

// Call disableControls initially to disable them when the page loads
function disableControls() {
    document.querySelectorAll(".slider-group input").forEach((input) => {
        input.disabled = true
    })
}

document.getElementById("fileInput").addEventListener("change", uploadImage)

// auxiliary functions for the string manipulation
function matchCase(text, pattern) {
    let result = ""
    for (let i = 0; i < text.length; i++) {
        if (i < pattern.length && pattern[i] === pattern[i].toUpperCase()) {
            result += text[i].toUpperCase()
        } else {
            result += text[i].toLowerCase()
        }
    }
    return result
}

function get_overlay_masks() {
    let formData = new FormData()
    formData.append("imageId", "gray")

    fetch("/get-overlay-masks", { method: "POST", body: formData })
        .then((response) => response.json())
        .then((data) => {
            asphaltMaskURL = URL.createObjectURL(
                base64toBlob(data.asphalt_mask, "image/png"),
            )
            aggregateMaskURL = URL.createObjectURL(
                base64toBlob(data.aggregate_mask, "image/png"),
            )
            backgroundMaskURL = URL.createObjectURL(
                base64toBlob(data.background_mask, "image/png"),
            )
        })
        .catch((error) => {
            console.error("Error during mask fetch:", error)
        })
}

function get_image_grayscale() {
    fetch("/get-image-grayscale", { method: "GET" })
        .then((response) => response.json())
        .then((data) => {
            uploadedImageURL_gray = URL.createObjectURL(
                base64toBlob(data.gray, "image/png"),
            )
        })
        .catch((error) => {
            console.error("Error during image grayscle fetch:", error)
        })
}

function get_image_color() {
    fetch("/get-image-color", { method: "GET" })
        .then((response) => response.json())
        .then((data) => {
            uploadedImageURL_gray = URL.createObjectURL(
                base64toBlob(data.color, "image/png"),
            )
        })
        .catch((error) => {
            console.error("Error during image color fetch:", error)
        })
}

function get_images() {
    get_image_grayscale()
    get_image_color()
}

function inference() {
    const model_name = document.getElementById("inference_model").value
    let formData = new FormData()
    formData.append("model_name", model_name)

    const uniqueQuery = "?nocache=" + new Date().getTime()
    return fetch("/inference" + uniqueQuery, { method: "POST", body: formData })
        .then((response) => response.json())
        .then((data) => {
            if (data.status === "success") {
                //    uploadedImageOverlay.src = URL.createObjectURL(base64toBlob(data.asphalt_mask, 'image/png'));
                uploadedImageURL_mask_asphalt = URL.createObjectURL(
                    base64toBlob(data.asphalt_mask, "image/png"),
                )
                uploadedImageURL_mask_aggregate = URL.createObjectURL(
                    base64toBlob(data.aggregate_mask, "image/png"),
                )
                uploadedImageURL_mask_bg = URL.createObjectURL(
                    base64toBlob(data.background_mask, "image/png"),
                )

                uploadedImageOverlay_aggregate.src =
                    uploadedImageURL_mask_aggregate
                uploadedImageOverlay_asphalt.src = uploadedImageURL_mask_asphalt
                uploadedImageOverlay_bg.src = uploadedImageURL_mask_bg
            }
        })
        .catch((error) => {
            console.error("Error during inference:", error)
        })
}

document.querySelectorAll("#inference_model").forEach((element) => {
    element.addEventListener("change", function () {
        displayWorkingMessage()
        inference()
            .then(() => {
                redrawCanvases()
            })
            .then(() => removeWorkingMessage())
    })
})

async function uploadImage() {
    displayWorkingMessage()

    const fileInput = document.getElementById("fileInput")
    if (fileInput.files.length === 0) return
    const file = fileInput.files[0]

    var formData = new FormData()
    formData.append("file", file)

    const uniqueQuery = "?nocache=" + new Date().getTime()
    const url = URL.createObjectURL(file)
    uploadedImageURL_color = url

    // fetch('/process-image-demo' + uniqueQuery, { method: 'POST', body: formData })
    fetch("/process-image" + uniqueQuery, { method: "POST", body: formData })
        // .then(response => console.log(response))
        .then((response) => response.json())
        .then((data) => {
            uploadedImageURL_color = URL.createObjectURL(
                base64toBlob(data.color, "image/png"),
            )
        })
        .then(() => inference())
        .then(() => removeWorkingMessage())
        .then(() => {
            document.getElementById("defaultImage").style.display = "none"
        })
        .then(() => getImageType())
        .then(() => enableControls())
        .then(() => console.log("Image processed successfully."))
        .catch((error) => {
            console.error("Error:", error)
            // alert("Error processing image: " + error.message)
            removeWorkingMessage()
        })
}

function TF(a) {
    return new Promise((resolve, reject) => {
        try {
            a = !a
            resolve(a)
        } catch (error) {
            reject(error)
        }
    })
}

async function changeDisplayAsphalt() {
    displayAsphaltMask = await TF(displayAsphaltMask)
    redrawCanvases()
}

async function changeDisplayAggregate() {
    displayAggregateMask = await TF(displayAggregateMask)
    redrawCanvases()
}

async function changeDisplayBackground() {
    displayBackgroundMask = await TF(displayBackgroundMask)
    redrawCanvases()
}

function getImageType() {
    let imageType = document.getElementById("imageType").value
    switch (imageType) {
        case "original":
            uploadedImage.src = uploadedImageURL_color
            break
        case "original_no_bg":
            uploadedImage.src = uploadedImageURL_nobg
            break
        case "bw":
            uploadedImage.src = uploadedImageURL_gray
            break
    }

    if (displayAsphaltMask) {
        console.log("Displaying asphalt mask")
        uploadedImageOverlay_asphalt.src = uploadedImageURL_mask_asphalt
        document.getElementById("overlayCanvasAsphalt").style.display = "block"
        document.getElementById("overlayCanvasAsphalt").style.opacity =
            labelSettings.mask_opacity
    } else {
        document.getElementById("overlayCanvasAsphalt").style.display = "none"
    }
    if (displayAggregateMask) {
        uploadedImageOverlay_aggregate.src = uploadedImageURL_mask_aggregate
        document.getElementById("overlayCanvasAggregate").style.display =
            "block"
        document.getElementById("overlayCanvasAggregate").style.opacity =
            labelSettings.mask_opacity
    } else {
        document.getElementById("overlayCanvasAggregate").style.display = "none"
    }
    if (displayBackgroundMask) {
        uploadedImageOverlay_bg.src = uploadedImageURL_mask_bg
        document.getElementById("overlayCanvasBackground").style.display =
            "block"
        document.getElementById("overlayCanvasBackground").style.opacity =
            labelSettings.mask_opacity
    } else {
        document.getElementById("overlayCanvasBackground").style.display =
            "none"
    }
}

// this function displays a "working" message on the page while the image is being processed
function displayWorkingMessage() {
    let workingMessage = document.getElementById("workingMessage")
    workingMessage.style.display = "block"
}
// this function removes the "working" message from the page
function removeWorkingMessage() {
    let workingMessage = document.getElementById("workingMessage")
    workingMessage.style.display = "none"
}

function magnify(imgID, zoom) {
    var img, glass, w, h, bw
    img = document.getElementById(imgID)
    glass = document.createElement("DIV")
    glass.setAttribute("class", "img-magnifier-glass")
    img.parentElement.insertBefore(glass, img)

    // Setup the properties for the magnifying glass
    if (img.tagName === "CANVAS") {
        glass.style.backgroundImage = "url('" + img.toDataURL() + "')"
    } else {
        // for image
        glass.style.backgroundImage = "url('" + img.src + "')"
    }
    glass.style.backgroundRepeat = "no-repeat"
    glass.style.backgroundSize =
        img.clientWidth * zoom + "px " + img.clientHeight * zoom + "px"
    bw = 3
    w = glass.offsetWidth / 2
    h = glass.offsetHeight / 2

    // Function to move the magnifier glass with the mouse
    function moveMagnifier(e) {
        var pos, x, y
        e.preventDefault()
        pos = getCursorPos(e)
        x = pos.x
        y = pos.y

        // Update the position of the magnifier glass
        glass.style.left = x - w + "px"
        glass.style.top = y - h + "px"
        // Set the background position of the magnifier glass
        glass.style.backgroundPosition =
            "-" + (x * zoom - w + bw) + "px -" + (y * zoom - h + bw) + "px"
    }

    function getCursorPos(e) {
        var a,
            x = 0,
            y = 0
        e = e || window.event
        a = img.getBoundingClientRect()
        x = e.pageX - a.left - window.pageXOffset
        y = e.pageY - a.top - window.pageYOffset

        // since the canvas adjust its size to the screen, we need to scale the cursor position
        return { x: x, y: y }
    }

    // Add event listeners for moving and hiding the magnifier glass
    img.addEventListener("mousemove", moveMagnifier)
    glass.addEventListener("mousemove", moveMagnifier)

    // Improved handling for hiding the magnifying glass
    // Apply 'mouseleave' event to both image and glass
    img.addEventListener("mouseleave", function () {
        glass.style.visibility = "hidden"
    })
    glass.addEventListener("mouseleave", function () {
        glass.style.visibility = "hidden"
    })

    // Optional: Show the glass when entering the image area
    img.addEventListener("mouseenter", function () {
        glass.style.visibility = "visible"
    })

    img.addEventListener("mouseenter", function () {
        glass.style.visibility = "visible"
    })

    img.addEventListener("mousemove", moveMagnifier)
}

function removeMagnifier(imgID) {
    var img = document.getElementById(imgID)
    var glass = img.parentElement.getElementsByClassName(
        "img-magnifier-glass",
    )[0]
    if (glass) {
        glass.remove()
    }
}

function redrawCanvases() {
    if (uploadedImage.src) {
        getImageType()
    }
}

// Global event listeners
document
    .getElementById("redOverlayCheckbox")
    .addEventListener("change", function () {
        changeDisplayAsphalt()
    })
document
    .getElementById("aggregateOverlayCheckbox")
    .addEventListener("change", function () {
        changeDisplayAggregate()
    })
document
    .getElementById("backgroundOverlayCheckbox")
    .addEventListener("change", function () {
        changeDisplayBackground()
    })
document.getElementById("imageType").addEventListener("change", redrawCanvases)

async function evaluateExperiment() {
    const uniqueQuery = "?nocache=" + new Date().getTime()
    console.log("Evaluating the experiment...")
    fetch("/evaluate-asphalt" + uniqueQuery, { method: "GET" })
        .then((response) => response.json())
        .then((response) => {
            if (response.status === "error") {
                alert(response.message)
                throw new Error(response.message)
            } else if (response.status == "success") {
                // display only 2 decimal places;
                let displayNum = response.evaluation * 100
                displayNum = displayNum.toFixed(2)
                alert(
                    alerts.evaluationCompleted +
                        "\n" +
                        alerts.evaluationResults +
                        displayNum +
                        "%" +
                        "\n" +
                        alerts.evaluationDemo,
                )
            }
        })
}

document
    .getElementById("index_evaluation")
    .addEventListener("click", async function () {
        evaluateExperiment()
    })
window.addEventListener("resize", redrawCanvases) // this ensures the magnifying glass is redrawn when the window is resized

function changeOverlayOpacity() {
    let value = document.getElementById("opacitySlider").value
    document.getElementById("opacityValue").value = value
    labelSettings.mask_opacity = value / 100
    redrawCanvases()
}

document
    .getElementById("opacitySlider")
    .addEventListener("change", changeOverlayOpacity)
document.getElementById("opacityValue").addEventListener("change", function () {
    let value = Math.min(100, Math.max(0, parseInt(this.value)))
    document.getElementById("opacitySlider").value = value
    document.getElementById("opacityValue").value = value
    changeOverlayOpacity()
})

// keyboard shortcuts
document.addEventListener("keydown", function (event) {
    const eventKey = event.key.toLowerCase()
    // shif + ...
    switch (eventKey) {
        case "a":
            if (event.shiftKey) {
                document.getElementById("redOverlayCheckbox").checked =
                    !document.getElementById("redOverlayCheckbox").checked
                changeDisplayAsphalt()
            }
            break
        case "s":
            if (event.shiftKey) {
                document.getElementById("aggregateOverlayCheckbox").checked =
                    !document.getElementById("aggregateOverlayCheckbox").checked
                changeDisplayAggregate()
            }
            break
        case "d":
            if (event.shiftKey) {
                document.getElementById("backgroundOverlayCheckbox").checked =
                    !document.getElementById("backgroundOverlayCheckbox")
                        .checked
                changeDisplayBackground()
            }
            break
        case "e":
            // evaluate the experiment
            if (event.shiftKey) {
                evaluateExperiment()
            }
            break
    }
})

document.querySelectorAll(".custom-select").forEach((select) => {
    const trigger = select.querySelector(".select-trigger")
    trigger.addEventListener("click", () => {
        select.classList.toggle("open")
    })

    select.querySelectorAll(".option").forEach((option) => {
        option.addEventListener("click", () => {
            trigger.textContent = option.textContent + " ▼"
            select.classList.remove("open")
        })
    })
})
