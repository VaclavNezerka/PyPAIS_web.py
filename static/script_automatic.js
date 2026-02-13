import base64toBlob from "./utils.js"

const alerts = await fetch("/translations-alerts", { method: "GET" }).then(
    (response) => response.json(),
)
// global variables
let konvaStage
let staticUrl
let isDrawing = false
// let konvaLayer = new Konva.Layer();
// let konvaLayerMaskBg = new Konva.Layer();
// let konvaLayerMaskAsphalt = new Konva.Layer();
// let konvaLayerMaskAggregate = new Konva.Layer();

// let viewer = OpenSeadragon({
//     id: "viewer",
//     tileSize: 256,
//     minZoomLevel: 1,
//     maxZoomLevel: 8,
//     zoomInButton: "zoom-in",
//     zoomOutButton: "zoom-out",
//     homeButton: "home",
//     rotateLeftButton: "rotate-left",
//     rotateRightButton: "rotate-right",
//     showNavigator: true,
//     animationTime: 0.2,
//     preserveViewport: true,
//     // tileSources: {
//     //     type: 'image',
//     //     url: staticUrl
//     //   },
//       gestureSettingsMouse: {
//         scrollToZoom: true,
//         clickToZoom: false,
//       },
// });

function loadNewImage(newImageUrl) {
    viewer.open({
        type: "image",
        url: newImageUrl,
    })
}

// Initialize Konva.js overlay
// konvaStage = new Konva.Stage({
// container: 'viewer_konva',
// width: viewer.container.clientWidth,
// height: viewer.container.clientHeight,
// draggable: false,
// backgroundColor: 'transparent'
// });
// konvaStage.add(konvaLayer);

// Wait for the OpenSeadragon viewer to fully open the image
// viewer.addHandler('open', function() {
//     // Get the image dimensions from the OpenSeadragon world
//     const tiledImage = viewer.world.getItemAt(0); // Assuming only one image
//     const imageWidth = tiledImage.getContentSize().x; // Image width in pixels
//     const imageHeight = tiledImage.getContentSize().y; // Image height in pixels

//     // Now set the viewer container to match the image dimensions
//     const viewerElement = document.getElementById('viewer');
//     viewerElement.style.width = imageWidth + 'px';
//     viewerElement.style.height = imageHeight + 'px';

//     // Optionally resize the Konva container to match the viewer
//     const konvaContainer = document.getElementById('viewer_konva');
//     konvaContainer.style.width = imageWidth + 'px';
//     konvaContainer.style.height = imageHeight + 'px';

//     // Adjust Konva stage size accordingly
//     konvaStage.width(imageWidth);
//     konvaStage.height(imageHeight);
//     konvaLayer.batchDraw();
// });

// Trigger initial sync
// viewer.viewport.zoomTo(1);
// viewer.viewport.panTo(new OpenSeadragon.Point(0, 0));
// konvaStage.scale({ x: 1, y: 1 });

let uploadedImageURL_color = null
let uploadedImageURL_gray = null
let uploadedImageURL_nobg = null

let uploadedImageURL_mask_aggregate = null
let uploadedImageURL_mask_asphalt = null
let uploadedImageURL_mask_bg = null

let uploadedImageURL_gray_blur = null
let uploadedImageURL_nobg_blur = null

let uploadedImageURL_redOverlay = null
let entropyURL = null
let uploadedImage = new Image()
let uploadedImageOverlay = new Image()
let uploadedImageOverlay_asphalt = new Image()
let uploadedImageOverlay_aggregate = new Image()
let uploadedImageOverlay_bg = new Image()

function hexToRgba(hex, alpha = 1) {
    // Remove '#' if present
    hex = hex.replace("#", "")

    // Handle shorthand (#abc)
    if (hex.length === 3) {
        hex = hex
            .split("")
            .map((c) => c + c)
            .join("")
    }

    const r = parseInt(hex.slice(0, 2), 16)
    const g = parseInt(hex.slice(2, 4), 16)
    const b = parseInt(hex.slice(4, 6), 16)

    return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

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
bitumenColor = "rgba(255, 0, 0, 1)"
aggregateColor = "rgba(0, 0, 225, 1)"
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

// helper declarations because of the global scope
let grayscaleImageData = null
let originalEntropyImageData = null

// function getOpenseadragonSize() {
//     let viewer = document.getElementById('viewer_konva');
//     let viewerWidth = viewer.clientWidth;
//     let viewerHeight = viewer.clientHeight;
//     console.log('Width: ' + viewerWidth + ' Height: ' + viewerHeight);
//     return [viewerWidth, viewerHeight];
// }

// function resizeDragonRow() {
//     const shape = getOpenseadragonSize();
//     console.log('Width: ' + shape[0] + ' Height: ' + shape[1]);
//     let row = document.getElementById('dragon_row');
//     row.style.height = shape[0] + 'px';
// }

// function reshapeDragonAndCanvas() {
//     let shape = getOpenseadragonSize();
//     let konva = document.getElementById('viewer_konva');
//     let ctx = canvas.getContext('2d');
//     canvas.width = shape[0];
//     canvas.height = shape[1];
//     ctx.drawImage(uploadedImage, 0, 0, canvas.width, canvas.height);
//     if (displayAsphaltMask) {
//         ctx.drawImage(uploadedImageOverlay, 0, 0, canvas.width, canvas.height);
//     }
//     magnify('imageCanvas', 4);
//     resizeDragonRow();
//     initializeMask();
// }

// window.addEventListener('resize', reshapeDragonAndCanvas);

uploadedImage.onload = function () {
    var canvas = document.getElementById("imageCanvas")
    var ctx = canvas.getContext("2d", { willReadFrequently: true })
    // clear the canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    canvas.width = this.width
    canvas.height = this.height
    ctx.drawImage(this, 0, 0, canvas.width, canvas.height)
    // if (displayAsphaltMask) {
    //     // ctx.drawImage(uploadedImageOverlay, 0, 0, canvas.width, canvas.height);
    //         // Get the image array from the mask URL
    //         const img = new Image();
    //         img.src = uploadedImageURL_mask_asphalt;
    //         img.onload = function() {
    //             // create an array from the string
    //             const color = labelSettings.asphalt.fill; //rgba(0,255,0,0.2)
    //             let colorArray = color.match(/[\d.]+/g).map(Number);
    //             const maskImageData = colorizeMask(imgArray, colorArray);
    //             createImageBitmap(maskImageData).then((bitmap) => {
    //                 ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    //             });
    //         };
    //         // // const maskImageData = createImageBitmap(colorizeMask(imgArray, colorArray));
    //         // const maskImageData = colorizeMask(imgArray, colorArray);
    //         // // const data = maskImageData.data; // Uint8ClampedArray [r,g,b,a, r,g,b,a, ...]
    //         // createImageBitmap(maskImageData).then((bitmap) => {
    //         //     ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    //         // });
    // }
    magnify("imageCanvas", labelSettings.magnify)

    // loadNewImage(uploadedImage.src);
    // resizeDragonRow();
    // initializeMask();
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

//     canvas.width = this.width ;
//     canvas.height = this.height ;
//     ctx.drawImage(this, 0, 0, canvas.width, canvas.height);
//     const color = labelSettings.asphalt.fill; //rgba(0,255,0,0.2)
//     ctx.drawImage(this, 0, 0, canvas.width, canvas.height);

//     // create an array from the string
//     let colorArray = color.match(/[\d.]+/g).map(Number);
//     const imgArray = ctx.getImageData(0, 0, canvas.width, canvas.height);
//     // const maskImageData = createImageBitmap(colorizeMask(imgArray, colorArray));
//     const maskImageData = colorizeMask(imgArray, colorArray);
//     // const data = maskImageData.data; // Uint8ClampedArray [r,g,b,a, r,g,b,a, ...]
//     createImageBitmap(maskImageData).then((bitmap) => {
//         ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
//     });
//     magnify('overlayCanvas', labelSettings.magnify);
// };

uploadImage.onerror = function () {
    console.error("Failed to load image at URL: " + this.src)
    console.error
}

// uploadedImageOverlay_asphalt.onload = () => {
//     var canvas = document.getElementById('overlayAsphalt');
//     var ctx = canvas.getContext('2d', { willReadFrequently: true });
//     canvas.width = uploadedImageOverlay_asphalt.width;
//     canvas.height = uploadedImageOverlay_asphalt.height;
//     ctx.drawImage(uploadedImageOverlay_asphalt, 0, 0);

//     let maskImageData = ctx.getImageData(0, 0, uploadedImageOverlay_asphalt.width, uploadedImageOverlay_asphalt.height);
//     maskImageData = colorizeMask(maskImageData, labelSettings.asphalt.fill);
//     ctx.putImageData(maskImageData, 0, 0);
//     canvas.style.display = 'block';
//     canvas.style.opacity = 0.5;
//     magnify('overlayCanvas', 4);
// };

let requestedImage = null
let displayImageBlur = false
let displayAsphaltMask = false
let displayAggregateMask = false
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

function replaceKeepCase(str, search, replace) {
    const regex = new RegExp(search, "gi")
    return str.replace(regex, (match) => {
        return matchCase(replace, match)
    })
}

// add event listeners to update info fields

init_info_listeners()
function init_info_listeners() {
    for (const id of [
        "info_sample_collection_data",
        "info_place_of_experiment",
        "info_test_procedure",
        "info_wrapping_temperature",
        "info_exposing_water_temperature",
        "info_datetime",
        "info_comment",
        "info_aggregate",
        "info_binder",
    ]) {
        document.getElementById(id).addEventListener("change", function () {
            console.log("Updating info field: " + id)
            let value = this.value
            console.log("New value: " + value)
            var formData = new FormData()
            formData.append(id, value)
            const uniqueQuery = "?nocache=" + new Date().getTime()
            fetch("/update_value/" + id + uniqueQuery, {
                method: "POST",
                body: formData,
            })
        })
    }
}

// document
//     .getElementById("info_sample_collection")
//     .addEventListener("change", function () {
//         let value = this.value
//         var formData = new FormData()
//         formData.append("info", value)
//         const uniqueQuery = "?nocache=" + new Date().getTime()
//         fetch("/update_value/info" + uniqueQuery, {
//             method: "POST",
//             body: formData,
//         })
//     })

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

function unlockControls() {
    // Find all sliders and input boxes and enable them
    document.querySelectorAll(".slider-group input").forEach((input) => {
        input.disabled = false
    })
}

function inference() {
    const model_name = document.getElementById("model").value
    let formData = new FormData()
    formData.append("model_name", model_name)

    const uniqueQuery = "?nocache=" + new Date().getTime()
    fetch("/inference" + uniqueQuery, { method: "POST", body: formData })
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

function colorizeMask(maskImageData, color = [255, 0, 0]) {
    const data = maskImageData.data // Uint8ClampedArray [r,g,b,a, r,g,b,a, ...]

    for (let i = 0; i < data.length; i += 4) {
        const a = data[i + 3]
        const on = a > 127 // opacity threshold to determine if the pixel is "on"

        if (on) {
            if (Array.isArray(color) && color.length === 4) {
                data[i] = color[0] // R
                data[i + 1] = color[1] // G
                data[i + 2] = color[2] // B
            }
            data[i + 3] = 255 // A (fully opaque)
        } else {
            // transparent background
            data[i + 3] = 0
        }
    }

    return maskImageData
}

function overlayMask(baseUrl, maskUrl) {
    const base = new Image()
    const mask = new Image()

    Promise.all([
        new Promise((r) => {
            base.onload = r
            base.src = baseUrl
        }),
        new Promise((r) => {
            mask.onload = r
            mask.src = maskUrl
        }),
    ]).then(() => {
        const canvas = document.getElementById("imageCanvas")
        const ctx = canvas.getContext("2d")
        canvas.width = base.width
        canvas.height = base.height

        ctx.drawImage(base, 0, 0)
        ctx.drawImage(mask, 0, 0)
    })
}

async function uploadImage() {
    displayWorkingMessage()

    const now = new Date()
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset())

    document.getElementById("info_datetime").value = now
        .toISOString()
        .slice(0, 16)
    document.getElementById("info_datetime").dispatchEvent(new Event("change"))

    fetch("/get-default-experiment-info")
        .then((response) => response.json())
        .then((data) => {
            if (data.status === "success") {
                // loop through data and set value of input with id of key to value
                for (const [key, value] of Object.entries(data.data)) {
                    const input = document.getElementById(key)
                    if (input) {
                        input.value = value
                        if (value) {
                            input.classList.add("has-value")
                        } else {
                            input.classList.remove("has-value")
                        }
                        input.dispatchEvent(new Event("change"))
                    }
                }
            }
        })

    const fileInput = document.getElementById("fileInput")
    if (fileInput.files.length === 0) return
    const file = fileInput.files[0]

    var formData = new FormData()
    formData.append("file", file)

    const uniqueQuery = "?nocache=" + new Date().getTime()
    const url = URL.createObjectURL(file)
    uploadedImageURL_color = url

    fetch("/process-image" + uniqueQuery, { method: "POST", body: formData })
        // .then(response => console.log(response))
        .then((response) => response.json())
        .then((data) => {
            uploadedImageURL_color = URL.createObjectURL(
                base64toBlob(data.color, "image/png"),
            )
            uploadedImageURL_gray = URL.createObjectURL(
                base64toBlob(data.gray, "image/png"),
            )
        })
        .then(() => inference())
        .then(() => removeWorkingMessage())
        .then(() => {
            document.getElementById("defaultImage").style.display = "none"
        })
        .then(() => getImageType())
        .then(() => unlockControls())
        .then(() => console.log("Image processed successfully."))
        .then(() => {
            console.log("Image loaded, fetching default experiment info...")
            getDefaultExperimentInfo().then((data) => {
                populateExperimentInfo(data)
            })
        })
        .catch((error) => {
            console.error("Error:", error)
            // alert("Error processing image: " + error.message)
            removeWorkingMessage()
        })

    // await removeBackground(formData)
    // await fetchGrayscaleData(formData)
    // .then(() => processImage())
    // .then(() => getImageType())
    // .then(() => enableControls()) // Enable controls after everything is loaded
    // .then(() => removeWorkingMessage())
    // .then(() => fetch('/save' + uniqueQuery, { method: 'POST' }))
    // .catch(error => {
    //     console.error('Error:', error);
    // });
}

function removeBackground(formData) {
    return new Promise((resolve, reject) => {
        const uniqueQuery = "?nocache=" + new Date().getTime()
        fetch("/remove-background" + uniqueQuery, {
            method: "POST",
            body: formData,
        })
            .then((response) => response.json())
            .then((data) => {
                let url = URL.createObjectURL(
                    base64toBlob(data.nobg, "image/png"),
                )
                uploadedImageURL_nobg = url
                if (uploadedImageURL_nobg_blur == null) {
                    uploadedImageURL_nobg_blur = url
                }
                let url2 = URL.createObjectURL(
                    base64toBlob(data.original_image, "image/png"),
                )
                uploadedImageURL_color = url2
                resolve()
            })
            .catch((error) => {
                console.error("Error:", error)
                reject(error)
            })
    })
}

function fetchGrayscaleData(formData) {
    return new Promise((resolve, reject) => {
        const uniqueQuery = "?nocache=" + new Date().getTime()
        fetch("/grayscale-data" + uniqueQuery, {
            method: "POST",
            body: formData,
        })
            .then((response) => response.blob())
            .then((blob) => {
                let url = URL.createObjectURL(blob)
                uploadedImageURL_gray = url
                if (uploadedImageURL_gray_blur == null) {
                    uploadedImageURL_gray_blur = url
                }
            })
            .then(() => {
                resolve()
            })
            .catch((error) => {
                console.error("Error:", error)
                reject(error)
            })
    })
}

function fetchOriginalEntropyData() {
    return new Promise((resolve, reject) => {
        var formData = new FormData()

        const uniqueQuery = "?nocache=" + new Date().getTime()
        fetch("/entropy" + uniqueQuery, { method: "POST", body: formData })
            .then((response) => response.blob())
            .then((blob) => {
                var url = URL.createObjectURL(blob)
                var img = new Image()
                img.onload = function () {
                    var canvas = document.createElement("canvas")
                    var ctx = canvas.getContext("2d")
                    canvas.width = img.width
                    canvas.height = img.height
                    ctx.drawImage(img, 0, 0)

                    originalEntropyImageData = ctx.getImageData(
                        0,
                        0,
                        canvas.width,
                        canvas.height,
                    )
                    // drawEntropyHistogram(); // Draw the histogram using the fetched entropy data
                    resolve() // Resolve the promise after the histogram is drawn
                }
                img.onerror = reject // Reject the promise on error
                img.src = url
            })
            .catch((error) => {
                console.error("Error:", error)
                reject(error) // Reject the promise on fetch error
            })
    })
}

function processImage() {
    return new Promise((resolve, reject) => {
        var formData = new FormData()
        formData.append("imageId", "gray")

        const uniqueQuery = "?nocache=" + new Date().getTime()
        fetch("/apply-mask" + uniqueQuery, { method: "POST", body: formData })
            .then((response) => response.json())
            .then((data) => {
                let overlayBlob = base64toBlob(data.overlay, "image/png")
                let entropyBlob = base64toBlob(data.entropy, "image/png")
                uploadedImageURL_redOverlay = URL.createObjectURL(overlayBlob)
                // uploadedImageOverlay.src = uploadedImageURL_redOverlay;
                uploadedImageOverlay_asphalt.src = uploadedImageURL_redOverlay
                entropyURL = URL.createObjectURL(entropyBlob)
                resolve()
            })
            // .then( () => {getImageType()})
            .catch((error) => {
                console.error("Error:", error)
                reject(error)
            })
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

    // const overlays = [
    //     { display: displayAsphaltMask, img: uploadedImageOverlay_asphalt, url: uploadedImageURL_mask_asphalt, id: 'overlayCanvasAsphalt' },
    //     { display: displayAggregateMask, img: uploadedImageOverlay_aggregate, url: uploadedImageURL_mask_aggregate, id: 'overlayCanvasAggregate' },
    //     { display: displayBackgroundMask, img: uploadedImageOverlay_bg, url: uploadedImageURL_mask_bg, id: 'overlayCanvasBackground' }
    // ];

    // overlays.forEach(({ display, img, url, id }) => {
    //     const el = document.getElementById(id);
    //     if (display) {
    //         img.src = url;
    //         el.style.display = 'block';
    //         el.style.opacity = labelSettings.mask_opacity;
    //     } else {
    //         el.style.display = 'none';
    //     }
    // });

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

async function validateAndUpdate() {
    displayWorkingMessage()
    await processImage()
    // await drawEntropyHistogram();
    // await drawIntensityHistogram();
    redrawCanvases()
    removeWorkingMessage()
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

function activateExperiment() {
    return new Promise((resolve, reject) => {
        // TODO: Control this function
        const uniqueQuery = "?nocache=" + new Date().getTime()
        fetch("/activate-experiment" + uniqueQuery, { method: "POST" })
            .then((response) => response.json())
            .then((data) => {
                if (data.status === "success") {
                    resolve()
                } else {
                    reject()
                }
            })
            .catch((error) => {
                console.error("Error:", error)
                reject()
            })
    })
}

function deactivateCurrentExperiment() {
    return new Promise((resolve, reject) => {
        fetch("is-experiment-active", { method: "GET" })
            .then((response) => response.json())
            .then((data) => {
                console.log(data)
                if (data.active === false) {
                    resolve()
                } else {
                    return fetch(
                        "/deactivate-experiment/" + String(data.experimentId),
                        { method: "POST" },
                    )
                }
            })
            .then((response) => response.json())
            .then((data) => {
                if (data.status === "success") {
                    resolve()
                } else {
                    reject()
                }
            })
            .catch((error) => {
                console.error("Error:", error)
                reject()
            })
    })
}

function loadExperiment(id) {
    displayWorkingMessage()
    fetch("/load-experiment/" + String(id), { method: "GET" })
        .then((response) => response.json())
        // .then(data => console.log(data))
        .then((data) => {
            console.log(data)
            if (data.status === "error") {
                alert(alerts.noExperiment)
                removeWorkingMessage()
                return
            }
            // if (data.expertGuess !== "NaN") {
            //     document.getElementById("expertGuess").value = Math.round(
            //         data.expert_guess * 100,
            //     )
            // }
            console.log("Setting expert guess to: " + data.expert_guess)
            if (data.expertGuess !== null && !isNaN(data.expert_guess)) {
                if (data.expert_guess > 0) {
                    document.getElementById("expertGuess").value = Math.round(
                        data.expert_guess * 100,
                    )
                }
            }

            for (const id of [
                "info_sample_collection_data",
                "info_place_of_experiment",
                "info_test_procedure",
                "info_wrapping_temperature",
                "info_exposing_water_temperature",
                "info_datetime",
                "info_comment",
                "info_aggregate",
                "info_binder",
            ]) {
                if (data[id]) {
                    document.getElementById(id).value = data[id]
                }
            }
            // document.getElementById("info").value = data.info

            // set the image URLs
            uploadedImageURL_color = URL.createObjectURL(
                base64toBlob(data.color, "image/png"),
            )
            uploadedImageURL_gray = URL.createObjectURL(
                base64toBlob(data.gray, "image/png"),
            )
            // set overlay mask URLs
            // uploadedImageURL_mask_asphalt = URL.createObjectURL(base64toBlob(data.asphalt_mask, 'image/png'));
            // uploadedImageURL_mask_aggregate = URL.createObjectURL(base64toBlob(data.aggregate_mask, 'image/png'));
            // uploadedImageURL_mask_bg = URL.createObjectURL(base64toBlob(data.background_mask, 'image/png'));
        })
        .then(() => {
            document.getElementById("defaultImage").style.display = "none"
        })
        .then(() => inference())
        .then(() => getImageType())
        .then(() => enableControls()) // Enable controls after everything is loaded
        .catch((error) => {
            console.error("Error:", error)
        })
        .finally(() => removeWorkingMessage())
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
    console.log("Starting evaluation...")
    if (document.getElementById("expertGuess").value === "") {
        alert(
            // "Please fill the expert guess field before evaluating the experiment."
            alerts.expertGuessEmpty,
        )
        return
    } else {
        const uniqueQuery = "?nocache=" + new Date().getTime()
        console.log("Evaluating the experiment...")
        fetch("/evaluate-asphalt" + uniqueQuery, { method: "POST" })
            .then((response) => response.json())
            .then((response) => {
                // display only 2 decimal places;
                let displayNum = response.evaluation * 100
                displayNum = displayNum.toFixed(2)
                alert(
                    alerts.evaluationCompleted +
                        "\n" +
                        alerts.evaluationResults +
                        displayNum +
                        "%",
                )
            })
            .then(() => deactivateCurrentExperiment())
            .then(() => {
                // redirect to the '/' page
                window.location.href = "/"
            })
    }
}

document
    .getElementById("index_evaluation")
    .addEventListener("click", async function () {
        evaluateExperiment()
    })
// window.addEventListener('resize', function() { magnify('imageCanvas', 4); }); // this ensures the magnifying glass is redrawn when the window is resized
window.addEventListener("resize", redrawCanvases) // this ensures the magnifying glass is redrawn when the window is resized

// when the user leaves the expertGuess field and the value is not empty, the min and max values will be updated
document.getElementById("expertGuess").addEventListener("change", function () {
    let value = this.value
    if (value !== "") {
        // convert to number
        value = Number(value)
        if (value < 0) {
            this.value = 0
        } else if (value > 100) {
            this.value = 100
        }
        value = this.value
        // send the value to the server
        var formData = new FormData()
        formData.append("expert_guess", value / 100)
        const uniqueQuery = "?nocache=" + new Date().getTime()
        fetch("/update_value/expert_guess" + uniqueQuery, {
            method: "POST",
            body: formData,
        })
    }
    console.log("Expert guess changed to: " + value)
})

// if the user visits the page '/' and the experiment is active, load the experiment

initPage()
function initPage() {
    console.log("Running on DOMContentLoaded event")
    fetch("/is-experiment-active")
        .then((response) => response.json())
        .then((data) => {
            console.log(data)
            if (data.active === true) {
                console.log(
                    "Experiment is active. Loading experiment data...",
                    data.experimentId,
                )
                loadExperiment(data.experimentId)
            }
        })
}

function changeOverlayOpacity() {
    let value = document.getElementById("opacitySlider").value
    document.getElementById("opacityValue").value = value
    labelSettings.mask_opacity = value / 100
    // if (displayed_mask) {
    //     displayed_mask.style.opacity = value / 100;
    // }
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
    // Prevents an error when event.key is undefined (e.g., when confirming auto-fill prompts )
    if (!event.key) {
        return
    }
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
        case "c":
            if (event.shiftKey) {
                // change the image type
                let imageType = document.getElementById("imageType")
                imageType.selectedIndex =
                    (imageType.selectedIndex + 1) % imageType.options.length
                redrawCanvases()
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

function getFormattedDateTime() {
    const now = new Date()
    const year = now.getFullYear()
    const month = String(now.getMonth() + 1).padStart(2, "0")
    const day = String(now.getDate()).padStart(2, "0")
    const hours = String(now.getHours()).padStart(2, "0")
    const minutes = String(now.getMinutes()).padStart(2, "0")
    return `${year}-${month}-${day} ${hours}:${minutes}`
}

async function getDefaultExperimentInfo() {
    return new Promise((resolve, reject) => {
        const uniqueQuery = "?nocache=" + new Date().getTime()
        fetch("/default-experiment-info" + uniqueQuery, { method: "GET" })
            .then((response) => response.json())
            .then((data) => {
                data.datetime = getFormattedDateTime()
                console.log("Default experiment info:", data)
                resolve(data)
            })
            .catch((error) => {
                // console.error("Error:", error)
                reject(error)
            })
    })
}

function populateExperimentInfo(info) {
    document.getElementById("info_datetime").value = info.datetime
    document.getElementById("info_sample_collection_data").value =
        info.info_sample_collection_data
    document.getElementById("info_place_of_experiment").value =
        info.info_place_of_experiment
    document.getElementById("info_test_procedure").value =
        info.info_test_procedure
    document.getElementById("info_wrapping_temperature").value =
        info.info_wrapping_temperature
    document.getElementById("info_exposing_water_temperature").value =
        info.info_exposing_water_temperature
    document.getElementById("info_comment").value = info.info_comment
}

// import OpenSeadragon from "./openseadragon_5.0/openseadragon.min.js";

// let pointHistory = [];
// let waitingForApproval = false;

// allocate the urls for the masks bg, aggregate, and asphalt
// let mask_bg = null;
// let mask_aggregate = null;
// let mask_asphalt = null;
// let displayed_mask = null;

// Initialize OpenSeadragon viewer
// const viewer = OpenSeadragon({
//     id: "viewer",
//     tileSize: 256,
//     minZoomLevel: 1,
//     maxZoomLevel: 8,
//     zoomInButton: "zoom-in",
//     zoomOutButton: "zoom-out",
//     homeButton: "home",
//     rotateLeftButton: "rotate-left",
//     rotateRightButton: "rotate-right",
//     showNavigator: true,
//     animationTime: 0.2,
//     preserveViewport: true,
//     tileSources: {
//         type: 'image',
//         url: staticUrl
//       },
//       gestureSettingsMouse: {
//         scrollToZoom: true,
//         clickToZoom: false,
//       },
// });

/*
const viewerMask = document.createElement('canvas');
viewerMask.id = 'viewerMaskCanvas';
viewerMask.width = viewer.container.clientWidth;
viewerMask.height = viewer.container.clientHeight;
document.getElementById('viewer_mask').appendChild(viewerMask);

const maskContext = viewerMask.getContext('2d');
const maskImage = new Image();
// maskImage.src = mask_bg;
maskImage.onload = function() {
    maskContext.drawImage(maskImage, 0, 0, viewerMask.width, viewerMask.height);
}; */

// // Wait for the OpenSeadragon viewer to fully open the image
//   viewer.addHandler('open', function() {
//     // Get the image dimensions from the OpenSeadragon world
//     const tiledImage = viewer.world.getItemAt(0); // Assuming only one image
//     const imageWidth = tiledImage.getContentSize().x; // Image width in pixels
//     const imageHeight = tiledImage.getContentSize().y; // Image height in pixels

//     // Now set the viewer container to match the image dimensions
//     const viewerElement = document.getElementById('viewer');
//     viewerElement.style.width = imageWidth + 'px';
//     viewerElement.style.height = imageHeight + 'px';

//     // Optionally resize the Konva container to match the viewer
//     const konvaContainer = document.getElementById('viewer_konva');
//     konvaContainer.style.width = imageWidth + 'px';
//     konvaContainer.style.height = imageHeight + 'px';

//     // Adjust Konva stage size accordingly
//     konvaStage.width(imageWidth);
//     konvaStage.height(imageHeight);
//     konvaLayer.batchDraw();
//   });

// // Initialize Konva.js overlay
// let konvaStage = new Konva.Stage({
//   container: 'viewer_konva',
//   width: viewer.container.clientWidth,
//   height: viewer.container.clientHeight,
//   draggable: false,
//   backgroundColor: 'transparent'
// });
// let isDrawing = false;
// let konvaLayer = new Konva.Layer();
// konvaStage.add(konvaLayer);
// let konvaLayerMaskBg = new Konva.Layer();
// let konvaLayerMaskAsphalt = new Konva.Layer();
// let konvaLayerMaskAggregate = new Konva.Layer();

// function setMaskFilter (kl, img, rgba) {
//   let konvaImage= new Konva.Image({
//     x: 0,
//     y: 0,
//     image: img,
//     width: document.getElementById('viewer').clientWidth,
//     height: document.getElementById('viewer').clientHeight
//   });
//   konvaImage.cache();
//   konvaImage.filters([Konva.Filters.RGBA]);
//   konvaImage.red(rgba[0]);
//   konvaImage.green(rgba[1]);
//   konvaImage.blue(rgba[2]);
//   konvaImage.alpha(rgba[3]);

//   konvaStage.add(kl);
//   kl.destroyChildren();
//   kl.add(konvaImage);

// }

// imageMaskBg.onload = function() {
//   //const rgba = labelSettings.background.fill.match(/\d+/g).map(Number);
//   let rgba = labelSettings.background.fill.match(/[\d.]+/g).map(Number);
//   rgba[3] = 1;
//   console.log(rgba);
//   setMaskFilter(konvaLayerMaskBg, imageMaskBg, rgba);
// };
// imageMaskAsphalt.onload = function() {
//   let rgba = labelSettings.asphalt.fill.match(/[\d.]+/g).map(Number);
//   rgba[3] = 1;
//   console.log(rgba);
//   setMaskFilter(konvaLayerMaskAsphalt, imageMaskAsphalt, rgba);
// };
// imageMaskAggregate.onload = function() {
//   let rgba = labelSettings.aggregate.fill.match(/[\d.]+/g).map(Number);
//   rgba[3] = 1;
//   console.log(rgba);
//   setMaskFilter(konvaLayerMaskAggregate,imageMaskAggregate, rgba);
// };

// // Draw polygons, rectangles, ellipses based on active tool
// let activeTool = 'polygon';  // Default tool
// let activeLabel = 'background';
// let startPoint = null;  // Track the start point of the shape
// let currentShape = null;

//   function flattenPoints(points) {
//     return points.map(point => {
//       return [point.x, point.y];
//     }).flat();
//   }

//   // Helper to create and draw shapes
//   function drawShape(points) {
//     if (waitingForApproval) {
//       return;
//     }
//     let shape;

//     points = flattenPoints(points);

//     switch (activeTool) {
//       case 'polygon':
//       shape = new Konva.Line({
//         points: points,
//         closed: true,
//         fill: labelSettings[activeLabel].fill,
//         stroke: labelSettings[activeLabel].stroke,
//         strokeWidth: labelSettings[activeLabel].strokeWidth,
//         lineJoin: 'round',
//         draggable: true
//       });
//       break;
//       case 'rectangle':
//             const width = Math.abs(points[0] - points[2]);
//             const height = Math.abs(points[1] - points[3]);
//             const x = Math.min(points[0], points[2]);
//             const y = Math.min(points[1], points[3]);
//             shape = new Konva.Rect({
//                 x: x,
//                 y: y,
//                 width: width,
//                 height: height,
//                 fill: labelSettings[activeLabel].fill,
//                 stroke: labelSettings[activeLabel].stroke,
//                 strokeWidth: labelSettings[activeLabel].strokeWidth,
//                 draggable: true
//                 });
//             break;
//         case 'ellipse':
//             if (points.length < 4) {
//               return;
//             }
//             let x_center = (points[0]+points[2])/2;
//             let y_center = (points[1]+points[3])/2;
//             let x_radius = Math.abs(points[0] - points[2])/2;
//             let y_radius = Math.abs(points[1] - points[3])/2;
//             if (points.length==6) {
//               y_radius = Math.abs(y_center - points[5]);
//             }
//               shape = new Konva.Ellipse({
//                 x: x_center,
//                 y: y_center,
//                 radius: {
//                   x: x_radius,
//                   y: y_radius,
//                   },
//                 fill: labelSettings[activeLabel].fill,
//                 stroke: labelSettings[activeLabel].stroke,
//                 strokeWidth: labelSettings[activeLabel].strokeWidth,
//                 draggable: true
//               });
//             break;
//             }

//             konvaLayer.add(shape);
//             konvaLayer.draw();
//             return shape;
// }

// function getImagePoint(position) {
//   const viewportPoint = viewer.viewport.pointFromPixel(position);
//   return viewer.viewport.viewportToImageCoordinates(viewportPoint);
// }

// function cancelAnnotation() {
//   pointHistory = [];
//   setTimeout(() => {
//     konvaLayer.destroyChildren();
//   }, 100);
// }

function initializeMask() {
    fetch("/get-corrected-mask", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({}),
    })
        .then((response) => response.json())
        .then((data) => {
            //   console.log('Mask data:', data);
            mask_bg = URL.createObjectURL(base64toBlob(data.bg, "image/png"))
            mask_aggregate = URL.createObjectURL(
                base64toBlob(data.aggregate, "image/png"),
            )
            mask_asphalt = URL.createObjectURL(
                base64toBlob(data.asphalt, "image/png"),
            )

            imageMaskBg.src = mask_bg
            imageMaskAsphalt.src = mask_asphalt
            imageMaskAggregate.src = mask_aggregate
        })
        .catch((error) => {
            console.error("Error initializing mask:", error)
        })
}

// function saveAnnotation() {
//   // Save the annotation data to a server
//   const annotationData = {
//     label: activeLabel,
//     shape: {
//       type: activeTool,
//       points: flattenPoints(pointHistory)
//     }
//   };

//   fetch('/save-annotation', {
//     method: 'POST',
//     headers: {
//       'Content-Type': 'application/json'
//     },
//     body: JSON.stringify(annotationData)
//   }).then(response => response.json())
//     .then(data => {
//       mask_bg = URL.createObjectURL(base64toBlob(data.bg, 'image/png'));
//       mask_aggregate = URL.createObjectURL(base64toBlob(data.aggregate, 'image/png'));
//       mask_asphalt = URL.createObjectURL(base64toBlob(data.asphalt, 'image/png'));

//       imageMaskBg.src = mask_bg;
//       imageMaskAsphalt.src = mask_asphalt;
//       imageMaskAggregate.src = mask_aggregate;

//       /*
//       let canvas = document.getElementById('viewerMaskCanvas');
//       image.onload = function() {
//         console.log('Image loaded:', image);
//         canvas.width = image.width;
//         canvas.height = image.height;
//         canvas.getContext('2d').drawImage(image, 0, 0);
//       };
//       console.log(mask_bg);
//       image.src = mask_aggregate;
//       */

//       console.log('Annotation saved:', data);
//     })
//     .catch(error => {
//       console.error('Error saving annotation:', error);
//     });

//   // clean out the annotation
//   pointHistory = [];
//   setTimeout(() => {
//     konvaLayer.destroyChildren();
//   }, 200);
// }

// // Click event to handle shape drawing
// viewer.addHandler('canvas-click', function (event) {
//   if (waitingForApproval) {
//     return;
//   }
//   const imagePoint = getImagePoint(event.position);

//   pointHistory.push({ x: imagePoint.x, y: imagePoint.y });
//   if (pointHistory.length==1) {
//     startPoint = pointHistory[0];
//     isDrawing = true;
//   }

//   if (pointHistory.length > 1) {
//     if (currentShape) {
//       currentShape.destroy();
//     }
//     switch (activeTool) {
//       case 'rectangle':
//           currentShape=drawShape(pointHistory);
//           startPoint = null;  // Reset after drawing
//           isDrawing = false;
//           waitingForApproval = true;
//           break;
//       case 'polygon':
//           currentShape=drawShape(pointHistory);
//           break;
//       case 'ellipse':
//           if (pointHistory.length==3) {
//             currentShape=drawShape(pointHistory);
//             startPoint = null;  // Reset after drawing
//             isDrawing = false;
//             waitingForApproval = true;
//             break;
//           }
//       break;

//     }
//   }
// });

// // Handle Enter key to finish the shape
// document.addEventListener('keydown', function (event) {
//   if (event.key === 'Enter' ) {
//     if (waitingForApproval) {
//       saveAnnotation();
//       waitingForApproval = false;
//     } else if (activeTool === 'polygon' && startPoint) {
//       // Finish the polygon by connecting the last point to the first point
//       konvaLayer.destroyChildren();
//       pointHistory.push(startPoint);
//       drawShape(pointHistory);
//       startPoint = null;  // Reset after finishing the shape
//       isDrawing = false;
//       waitingForApproval = true;
//     }
//   }
//   if (event.key === 'Escape') {
//     // Cancel the current shape drawing
//     currentShape.destroy();
//     konvaLayer.batchDraw();
//     startPoint = null;
//     isDrawing = false;
//     pointHistory = [];
//     if (waitingForApproval) {
//       cancelAnnotation();
//       waitingForApproval = false;
//     }
//   }
// });

// // Button Click Handlers for Tool Switching
// document.getElementById('polygon-btn').addEventListener('click', function () {
//     activeTool = 'polygon';
//     updateActiveButton('polygon-btn');
// });

// document.getElementById('rectangle-btn').addEventListener('click', function () {
//   activeTool = 'rectangle';
//   updateActiveButton('rectangle-btn');
//   });

//   document.getElementById('ellipse-btn').addEventListener('click', function () {
//     activeTool = 'ellipse';
//     updateActiveButton('ellipse-btn');
//     });

// document.getElementById('bgButton').addEventListener('click', () => {
// // Button Click Handlers for Labeling
//     const currentSettings = labelSettings['background'];
//     activeLabel = 'background';
//     const activeStroke = currentSettings.stroke;
//     const activeFill = currentSettings.fill;
// });

// document.getElementById('fgButton').addEventListener('click', () => {
//     activeLabel = 'aggregate';
//     });

// document.getElementById('asphaltButton').addEventListener('click', () => {
//       activeLabel = 'asphalt';
// });

// // Helper to activate a tool
// function updateActiveButton(activeBtnId) {
//   var buttons = document.querySelectorAll('.tool-btn');
//   buttons.forEach(button => button.classList.remove('active'));
//   document.getElementById(activeBtnId).classList.add('active');
//   }

// viewer.addHandler('viewport-change', function() {
// const zoom = viewer.viewport.getZoom();  // Get current zoom level from OpenSeadragon

// // Set scale for the Konva stage based on OpenSeadragon zoom level
// konvaStage.scale({ x: zoom, y: zoom });

// // Get the center of the OSD viewport (in viewport coordinates)
// const center = viewer.viewport.getCenter();

// // Convert OpenSeadragon center point (viewport coordinates) to Konva coordinates
// const imageCenter = viewer.viewport.viewportToImageCoordinates(center.x, center.y);

// // Adjust Konva stage position to match OSD viewport panning
// konvaStage.position({
//   x: -imageCenter.x * zoom + konvaStage.width() / 2,
//   y: -imageCenter.y * zoom + konvaStage.height() / 2
// });

// // Redraw the Konva layer efficiently after transformations
// konvaLayer.batchDraw();
// });

// // // Trigger initial sync
// // viewer.viewport.zoomTo(1);
// // viewer.viewport.panTo(new OpenSeadragon.Point(0, 0));
// // konvaStage.scale({ x: 1, y: 1 });

// function drawPreview(imagePoint) {
// if (currentShape) {
// currentShape.destroy();
// konvaLayer.batchDraw();
// }
// const pointSuggestions = pointHistory.concat({ x: imagePoint.x, y: imagePoint.y });
// currentShape = drawShape(pointSuggestions);
// }

// // Event handler for starting to draw
// addEventListener('mousemove', function (e) {
// if (isDrawing) {
// const offset = viewer.container.getBoundingClientRect();
// const position = new OpenSeadragon.Point(e.clientX-offset.left, e.clientY-offset.top);
// const imagePoint = getImagePoint(position);
// drawPreview(imagePoint);
// }
// });

// function adjustViewerSize() {
//     const viewerBox = document.getElementById("viewer_box");
//     const viewer = document.getElementById("viewer");
//     const konvaLayer = document.getElementById("viewer_konva");

//     // Set viewer and Konva layer width dynamically
//     const newWidth = viewerBox.clientWidCth;

//     viewer.style.width = `${newWidth}px`;
//     konvaLayer.style.width = `${newWidth}px`;
// }

// // Run on load and resize
// window.addEventListener("resize", adjustViewerSize);
// window.addEventListener("load", adjustViewerSize);
document
    .querySelector("#personalizeSettingsButton")
    .addEventListener("click", function () {
        window.location.href = "/useruser#personalized_settings"
        document.getElementById("experiment_info_section").scrollIntoView({
            behavior: "smooth",
        })
    })
