import base64toBlob from "./utils.js";

// global variables
let konvaStage;
let staticUrl;
let isDrawing = false;
let konvaLayer = new Konva.Layer();
let konvaLayerMaskBg = new Konva.Layer();
let konvaLayerMaskAsphalt = new Konva.Layer();
let konvaLayerMaskAggregate = new Konva.Layer();

let viewer = OpenSeadragon({
    id: "viewer",
    tileSize: 256,
    minZoomLevel: 1,
    maxZoomLevel: 8,
    zoomInButton: "zoom-in",
    zoomOutButton: "zoom-out",
    homeButton: "home",
    rotateLeftButton: "rotate-left",
    rotateRightButton: "rotate-right",
    showNavigator: true,
    animationTime: 0.2,
    preserveViewport: true,
    // tileSources: {
    //     type: 'image',
    //     url: staticUrl
    //   },
      gestureSettingsMouse: {
        scrollToZoom: true,
        clickToZoom: false,
      },
});

function loadNewImage(newImageUrl) {
    viewer.open({
        type: 'image',
        url: newImageUrl
    });
}    

// Initialize Konva.js overlay
konvaStage = new Konva.Stage({
container: 'viewer_konva',
width: viewer.container.clientWidth,
height: viewer.container.clientHeight,
draggable: false,
backgroundColor: 'transparent'
});
konvaStage.add(konvaLayer);

// Wait for the OpenSeadragon viewer to fully open the image
viewer.addHandler('open', function() {
// Get the image dimensions from the OpenSeadragon world
const tiledImage = viewer.world.getItemAt(0); // Assuming only one image
const imageWidth = tiledImage.getContentSize().x; // Image width in pixels
const imageHeight = tiledImage.getContentSize().y; // Image height in pixels

// Now set the viewer container to match the image dimensions
const viewerElement = document.getElementById('viewer');
viewerElement.style.width = imageWidth + 'px';
viewerElement.style.height = imageHeight + 'px';

// Optionally resize the Konva container to match the viewer
const konvaContainer = document.getElementById('viewer_konva');
konvaContainer.style.width = imageWidth + 'px';
konvaContainer.style.height = imageHeight + 'px';

// Adjust Konva stage size accordingly
konvaStage.width(imageWidth);
konvaStage.height(imageHeight);
konvaLayer.batchDraw();
});

// Trigger initial sync
viewer.viewport.zoomTo(1);
viewer.viewport.panTo(new OpenSeadragon.Point(0, 0));
konvaStage.scale({ x: 1, y: 1 });


let uploadedImageURL_color = null;
let uploadedImageURL_gray = null;
let uploadedImageURL_nobg = null;

let uploadedImageURL_color_blur = null;
let uploadedImageURL_gray_blur = null;
let uploadedImageURL_nobg_blur = null;

let uploadedImageURL_redOverlay = null;
let entropyURL = null;
let uploadedImage = new Image();
let uploadedImageOverlay = new Image();
let uploadedEntropyImage = new Image();

// helper declarations because of the global scope
let grayscaleImageData = null;
let originalEntropyImageData = null;

// IMAGE FUNCTIONS
uploadedEntropyImage.onload = function() {
    var canvas = document.getElementById('entropyCanvas');
    var ctx = canvas.getContext('2d');
    // clear the canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    canvas.width = this.width;
    canvas.height = this.height;
    ctx.drawImage(this, 0, 0, canvas.width, canvas.height);
    if (displayRedOverlay) {
        ctx.drawImage(uploadedImageOverlay, 0, 0, canvas.width, canvas.height);
    }
};
uploadedEntropyImage.onerror = function() {
    console.error("Failed to load image at URL: " + this.src);
    console.error;
};


function getOpenseadragonSize() {   
    let viewer = document.getElementById('viewer_konva');
    let viewerWidth = viewer.clientWidth;
    let viewerHeight = viewer.clientHeight;
    console.log('Width: ' + viewerWidth + ' Height: ' + viewerHeight);
    return [viewerWidth, viewerHeight];
}

function resizeDragonRow() {
    const shape = getOpenseadragonSize();
    console.log('Width: ' + shape[0] + ' Height: ' + shape[1]);
    let row = document.getElementById('dragon_row');
    row.style.height = shape[0] + 'px';
}


function reshapeDragonAndCanvas() {
    let shape = getOpenseadragonSize();
    let konva = document.getElementById('viewer_konva');
    let ctx = canvas.getContext('2d');
    canvas.width = shape[0];
    canvas.height = shape[1];
    ctx.drawImage(uploadedImage, 0, 0, canvas.width, canvas.height);
    if (displayRedOverlay) {
        ctx.drawImage(uploadedImageOverlay, 0, 0, canvas.width, canvas.height);
    }
    magnify('imageCanvas', 4);
    resizeDragonRow();
    initializeMask();
}

window.addEventListener('resize', reshapeDragonAndCanvas);

uploadedImage.onload = function() { 
    var canvas = document.getElementById('imageCanvas');
    var ctx = canvas.getContext('2d', { willReadFrequently: true });
    // clear the canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    canvas.width = this.width ;
    canvas.height = this.height ;
    ctx.drawImage(this, 0, 0, canvas.width, canvas.height);
    if (displayRedOverlay) {
        ctx.drawImage(uploadedImageOverlay, 0, 0, canvas.width, canvas.height);
    }            
    magnify('imageCanvas', 4);
    loadNewImage(uploadedImage.src);
    resizeDragonRow();
    initializeMask();


};
uploadImage.onerror = function() {
    console.error("Failed to load image at URL: " + this.src)
    console.error
};


let requestedImage = null;
let displayImageBlur = false; 
let displayRedOverlay = false; 

disableControls(); // Disable controls on page load

function enableControls() {
    // Find all sliders and input boxes and enable them
    document.querySelectorAll('.slider-group input').forEach(input => {
        input.disabled = false;
    });
}

// Call disableControls initially to disable them when the page loads
function disableControls() {
    document.querySelectorAll('.slider-group input').forEach(input => {
        input.disabled = true;
    });
}

document.getElementById('fileInput').addEventListener('change', uploadImage);

// auxiliary functions for the string manipulation
function matchCase(text, pattern) {
    let result = '';
    for (let i = 0; i < text.length; i++) {
        if (i < pattern.length && pattern[i] === pattern[i].toUpperCase()) {
            result += text[i].toUpperCase();
        } else {
            result += text[i].toLowerCase();
        }
    }
    return result;
}

function replaceKeepCase(str, search, replace) {
    const regex = new RegExp(search, 'gi');
    return str.replace(regex, (match) => {
        return matchCase(replace, match);
    });
}

// These listeners only update the mask, not the histogram
// Event listeners for intensity thresholds 1 - always higher than 0
function validateThresholds(id) {
    let input_value = document.getElementById(id).value;
    let val = Math.max(0, Math.min(255, parseInt(input_value)));
    // value/slider
    document.getElementById(id).value = val;
    const comp_id = id.includes('Value') ? id.replace('Value', 'Slider') : id.replace('Slider', 'Value');
    document.getElementById(comp_id).value = val;
    
    // the other slider id
    if (id.toLowerCase().includes('min')) {
        const mm_id = replaceKeepCase(id,'min', 'max');
        if (val > document.getElementById(mm_id).value) {
            document.getElementById(mm_id).value = val;
            document.getElementById(mm_id.replace('Value', 'Slider')).value = val;
            document.getElementById(mm_id.replace('Value', 'Slider')).dispatchEvent(new Event('change'));
            document.getElementById(mm_id).dispatchEvent(new Event('change'));
        }
    } else if (id.toLowerCase().includes('max')) {
        const mm_id = replaceKeepCase(id,'max', 'min');
        if (val < document.getElementById(mm_id).value) {
            document.getElementById(mm_id).value = val;
            document.getElementById(mm_id.replace('Value', 'Slider')).value = val;
            document.getElementById(mm_id).dispatchEvent(new Event('change'));
            document.getElementById(mm_id.replace('Value', 'Slider')).dispatchEvent(new Event('change'));
        }
    }   

    if (id.endsWith('1')){
        if (val < document.getElementById('minThresholdSlider0').value) {
            document.getElementById('minThresholdSlider0').value = val;
            document.getElementById('minThresholdValue0').value = val;
        }
        if (val <  document.getElementById('maxThresholdSlider0').value) {
            document.getElementById('maxThresholdSlider0').value = val;
            document.getElementById('maxThresholdValue0').value = val;
        }
    } else if (id.endsWith('0')) {
        if (val > document.getElementById('minThresholdSlider1').value) {
            document.getElementById('minThresholdSlider1').value = val;
            document.getElementById('minThresholdValue1').value = val;
        }
        if (val > document.getElementById('maxThresholdSlider1').value) {
            document.getElementById('maxThresholdSlider1').value = val;
            document.getElementById('maxThresholdValue1').value = val;
        }
    }
    validateAndUpdate();
}

function saveThresholds(id) {
    if (id.includes('entropy')) {
        fetch('/save_value/entropy_min_threshold', { method: 'POST' });
        fetch('/save_value/entropy_max_threshold', { method: 'POST' });
    } else {
        fetch('/save_value/intensity_min_threshold_0', { method: 'POST' });
        fetch('/save_value/intensity_max_threshold_0', { method: 'POST' });
        fetch('/save_value/intensity_min_threshold_1', { method: 'POST' });
        fetch('/save_value/intensity_max_threshold_1', { method: 'POST' });
        fetch('/save_value/entropy_min_threshold', { method: 'POST' });
        fetch('/save_value/entropy_max_threshold', { method: 'POST' });
    }
}

// 1 - intensity
document.getElementById('minThresholdSlider1').addEventListener('change', function() {
    validateThresholds('minThresholdSlider1');
    saveThresholds('minThresholdSlider1');
});
document.getElementById('minThresholdValue1').addEventListener('change', function() {
    validateThresholds('minThresholdValue1');
    saveThresholds('minThresholdValue1');
});
document.getElementById('maxThresholdSlider1').addEventListener('change', function() {
    validateThresholds('maxThresholdSlider1');
    saveThresholds('maxThresholdSlider1');
});
document.getElementById('maxThresholdValue1').addEventListener('change', function() {
    validateThresholds('maxThresholdValue1');
    saveThresholds('maxThresholdValue1');
});
// 0 - intensity
document.getElementById('minThresholdSlider0').addEventListener('change', function() {
    validateThresholds('minThresholdSlider0');
    saveThresholds('minThresholdSlider0');
});
document.getElementById('minThresholdValue0').addEventListener('change', function() {
    validateThresholds('minThresholdValue0');
    saveThresholds('minThresholdValue0');
});
document.getElementById('maxThresholdSlider0').addEventListener('change', function() {
    validateThresholds('maxThresholdSlider0');
    saveThresholds('maxThresholdSlider0');
});
document.getElementById('maxThresholdValue0').addEventListener('change', function() {
    validateThresholds('maxThresholdValue0');
    saveThresholds('maxThresholdValue0');
});
// Entopy
document.getElementById('entropyMinThresholdSlider').addEventListener('change', function() {
    validateThresholds('entropyMinThresholdSlider');
    saveThresholds('entropyMinThresholdSlider');
});
document.getElementById('entropyMinThresholdValue').addEventListener('change', function() {
    validateThresholds('entropyMinThresholdValue');
    saveThresholds('entropyMinThresholdValue');
});
document.getElementById('entropyMaxThresholdSlider').addEventListener('change', function() {
    validateThresholds('entropyMaxThresholdSlider');
    saveThresholds('entropyMaxThresholdSlider');
});
document.getElementById('entropyMaxThresholdValue').addEventListener('change', function() {
    validateThresholds('entropyMaxThresholdValue');
    saveThresholds('entropyMaxThresholdValue');
});

document.getElementById('blurValue').addEventListener('change', async function() {
    displayWorkingMessage();
    let admissibleVal = Math.max(0, Math.min(50, parseInt(this.value)));
    this.value = admissibleVal; // Correct the value in case it was out of bounds
    document.getElementById('blurSlider').value = this.value;
    document.getElementById('blurValue').value = this.value;
    await blurImage(this.value);
    fetch('/save_value/blur', { method: 'POST' })
    redrawCanvases();
    removeWorkingMessage();
});

document.getElementById('blurSlider').addEventListener('change', async function() {
    displayWorkingMessage();
    document.getElementById('blurValue').value = this.value;
    document.getElementById('blurSlider').value = this.value;
    await blurImage(this.value);
    fetch('/save_value/blur',{ method: 'POST' })
    redrawCanvases();
    removeWorkingMessage();
});


document.getElementById('info').addEventListener('change', function() {
    let value = this.value;
    var  formData = new FormData();
    formData.append('info', value);
    const uniqueQuery = '?nocache=' + new Date().getTime();
    fetch('/update_value/info' + uniqueQuery, { method: 'POST', body: formData })
});

async function uploadImage() {
    displayWorkingMessage();

    document.getElementById('blurSlider').value = 0;
    document.getElementById('blurValue').value = 0;
    const fileInput = document.getElementById('fileInput');
    if (fileInput.files.length === 0) return;
    const file = fileInput.files[0];

    var formData = new FormData();
    formData.append('file', file);

    const uniqueQuery = '?nocache=' + new Date().getTime();
    const url = URL.createObjectURL(file);
    uploadedImageURL_color = url;
    if (uploadedImageURL_color_blur === null) {
        uploadedImageURL_color_blur = url;
    }
    await removeBackground(formData)
    await fetchGrayscaleData(formData)

    .then(() => fetchOriginalEntropyData())
    .then(() => {document.getElementById('defaultImage').style.display = 'none';})
    .then(() => processImage())
    .then(() => processEntropyImage())
    .then(() => getImageType())
    .then(() => enableControls()) // Enable controls after everything is loaded
    .then(() => removeWorkingMessage())
    .then(() => fetch('/save' + uniqueQuery, { method: 'POST' }))
    .catch(error => {
        console.error('Error:', error);
    })
}

function removeBackground(formData) {
    return new Promise((resolve, reject) => {
        const uniqueQuery = '?nocache=' + new Date().getTime();
        fetch('/remove-background' + uniqueQuery, { method: 'POST', body: formData })
        .then(response => response.json())
        .then(data => {
            let url = URL.createObjectURL(base64toBlob(data.nobg, 'image/png'));
            uploadedImageURL_nobg = url;
            if (uploadedImageURL_nobg_blur == null) {
                uploadedImageURL_nobg_blur = url;
            }
            let url2 = URL.createObjectURL(base64toBlob(data.original_image, 'image/png'));
            uploadedImageURL_color = url2;
            if (uploadedImageURL_color_blur == null) {
                uploadedImageURL_color_blur = url2;
            }
            resolve();
        })
        .catch(error => {
            console.error('Error:', error);
            reject(error);
        });
    });
}



function fetchGrayscaleData(formData) {
    return new Promise((resolve, reject) => {
        const uniqueQuery = '?nocache=' + new Date().getTime();
        fetch('/grayscale-data' + uniqueQuery, { method: 'POST', body: formData })
        .then(response => response.blob())
        .then(blob => {
            let url = URL.createObjectURL(blob);
            uploadedImageURL_gray = url;
            if (uploadedImageURL_gray_blur == null) {
                uploadedImageURL_gray_blur = url;
            }
            createIntensityHistogram();
        })
        .then(() => { resolve(); })
        .catch(error => {
            console.error('Error:', error);
            reject(error);
        });
    });
}


function fetchOriginalEntropyData() {
    return new Promise((resolve, reject) => {
        var formData = new FormData();

        const uniqueQuery = '?nocache=' + new Date().getTime();
        fetch('/entropy' + uniqueQuery, { method: 'POST', body: formData })
        .then(response => response.blob())
        .then(blob => {
            var url = URL.createObjectURL(blob);
            var img = new Image(); 
            img.onload = function() {
                var canvas = document.createElement('canvas');
                var ctx = canvas.getContext('2d');
                canvas.width = img.width;
                canvas.height = img.height;
                ctx.drawImage(img, 0, 0);

                originalEntropyImageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                drawEntropyHistogram(); // Draw the histogram using the fetched entropy data
                resolve(); // Resolve the promise after the histogram is drawn
            };
            img.onerror = reject; // Reject the promise on error
            img.src = url;
        })
        .catch(error => {
            console.error('Error:', error);
            reject(error); // Reject the promise on fetch error
        });
    });
}


function processImage() {
    return new Promise((resolve, reject) => {
        var formData = new FormData();
        formData.append('minThreshold0', document.getElementById('minThresholdSlider0').value);
        formData.append('maxThreshold0', document.getElementById('maxThresholdSlider0').value);
        formData.append('minThreshold1', document.getElementById('minThresholdSlider1').value);
        formData.append('maxThreshold1', document.getElementById('maxThresholdSlider1').value);
        formData.append('entropyMinThreshold', document.getElementById('entropyMinThresholdSlider').value);
        formData.append('entropyMaxThreshold', document.getElementById('entropyMaxThresholdSlider').value);
        formData.append('imageId', 'gray');

        const uniqueQuery = '?nocache=' + new Date().getTime();
        fetch('/apply-mask'+uniqueQuery, { method: 'POST', body: formData })
        .then(response => response.json())  
        .then(data => {
                let overlayBlob = base64toBlob(data.overlay, 'image/png');
                let entropyBlob = base64toBlob(data.entropy, 'image/png');
                uploadedImageURL_redOverlay = URL.createObjectURL(overlayBlob);
                uploadedImageOverlay.src = uploadedImageURL_redOverlay;
                entropyURL = URL.createObjectURL(entropyBlob);
                resolve();
        })
        // .then( () => {getImageType()})
        .catch(error => {
            console.error('Error:', error);
            reject(error);
        });
});
}


function TF(a) {
return new Promise((resolve, reject) => {
    try {
    a = !a;
    resolve(a);
    } catch (error) {  
    reject(error);
    }
    }); 
}

async function changeSharpness() {
    displayImageBlur = await TF(displayImageBlur);
    redrawCanvases();
}

async function changeRedOverlay() {
    displayRedOverlay = await TF(displayRedOverlay);
    redrawCanvases();   
}

function processEntropyImage() {
    return new Promise((resolve, reject) => {
        var formData = new FormData();
        formData.append('minThreshold0', document.getElementById('minThresholdSlider0').value);
        formData.append('maxThreshold0', document.getElementById('maxThresholdSlider0').value);
        formData.append('minThreshold1', document.getElementById('minThresholdSlider1').value);
        formData.append('maxThreshold1', document.getElementById('maxThresholdSlider1').value);
        formData.append('entropyMinThreshold', document.getElementById('entropyMinThresholdSlider').value);
        formData.append('entropyMaxThreshold', document.getElementById('entropyMaxThresholdSlider').value);
        formData.append('imageId', 'entropy');

        const uniqueQuery = '?nocache=' + new Date().getTime();
        fetch('/apply-mask' + uniqueQuery, { method: 'POST', body: formData })
                .then(response => response.json())  
        .then(data => {
                let overlayBlob = base64toBlob(data.overlay, 'image/png');
                let entropyBlob = base64toBlob(data.entropy, 'image/png');
                uploadedImageURL_redOverlay = URL.createObjectURL(overlayBlob);
                uploadedImageOverlay.src = uploadedImageURL_redOverlay;
                entropyURL = URL.createObjectURL(entropyBlob);
                uploadedEntropyImage.src = entropyURL;
                resolve();
        })
        .catch(error => {
            console.error('Error:', error);
            reject(error);
        });
    });
}



function getImageType() {
            let imageType = document.getElementById('imageType').value;
            if (displayImageBlur) {
                switch (imageType) {
                    case 'original':
                        // delete the previous image
                        uploadedImage.src = uploadedImageURL_color_blur;
                        break;
                    case 'original_no_bg':
                        uploadedImage.src = uploadedImageURL_nobg_blur;
                        break;
                    case 'bw':
                        uploadedImage.src = uploadedImageURL_gray_blur;
                        break;
                }
            } else {    
                switch (imageType) {
                    case 'original':
                        uploadedImage.src = uploadedImageURL_color;
                        break;
                    case 'original_no_bg':
                        uploadedImage.src = uploadedImageURL_nobg;
                        break;
                    case 'bw':
                        uploadedImage.src = uploadedImageURL_gray;
                        break;
                }    
            } 
}


// this function displays a "working" message on the page while the image is being processed
function displayWorkingMessage() {
    let workingMessage = document.getElementById('workingMessage');
    workingMessage.style.display = 'block';
}
// this function removes the "working" message from the page
function removeWorkingMessage() {
    let workingMessage = document.getElementById('workingMessage');
    workingMessage.style.display = 'none';
}

// // this function converts a base64 string to a blob
// // the images are in a str64 format and it is decoded as a utf-8 string
// // we need to convert them to a blob
// function base64toBlob(base64, type) {
//     var byteString = atob(base64);
//     var ab = new ArrayBuffer(byteString.length);
//     var ia = new Uint8Array(ab);
//     for (var i = 0; i < byteString.length; i++) {
//         ia[i] = byteString.charCodeAt(i);
//     }
//     return new Blob([ab], { type: type });
// }


function blurImage(blurValue) {
    return new Promise((resolve, reject) => {
        var formData = new FormData();
        formData.append('blurValue', blurValue);
        const uniqueQuery = '?nocache=' + new Date().getTime();
        fetch('/blur' + uniqueQuery, { method: 'POST', body: formData })
        .then(response => {return response.json();})
        .then(data => {                        
            try {      
                // transfer str64 format to blob
                let colorBlob = base64toBlob(data.color, 'image/png');
                let grayBlob = base64toBlob(data.gray, 'image/png');
                let nobgBlob = base64toBlob(data.nobg, 'image/png');
        
                uploadedImageURL_color_blur = URL.createObjectURL(colorBlob);
                uploadedImageURL_gray_blur = URL.createObjectURL(grayBlob);
                uploadedImageURL_nobg_blur = URL.createObjectURL(nobgBlob);
            } catch (error) {
                console.error('An error occurred:', error);
            }
            
        })
        .then(() => fetchOriginalEntropyData())
        .then(() => processImage())
        .then(() => processEntropyImage())
        .then(() => {
            enableControls(); // Enable controls after everything is loaded
        })
        .then(() => {
            resolve();
        })
        .catch(error => {
            reject(error);
            console.error('Error:', error);
        })           
        ;
    });
}
    

async function validateAndUpdate() {
    displayWorkingMessage();
    await processImage();
    await processEntropyImage();
    await drawEntropyHistogram();
    await drawIntensityHistogram();
    redrawCanvases();
    removeWorkingMessage();
}

function drawIntensityHistogram() {
    // Assuming grayscaleImageData is already populated
    // if (!grayscaleImageData) {
    //     // wait for the grayscale image data to be loaded
    //     setTimeout(drawIntensityHistogram, 100);
    //     if (!grayscaleImageData) {
    //     return;
    //     }
    // }

    const canvas = document.getElementById('histogramCanvas');
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    const data = grayscaleImageData.data;
    let histogram = new Array(256).fill(0);
    for (let i = 0; i < data.length; i += 4) {
        const intensity = data[i];
        histogram[intensity]++;
    }
    const minThresholds = [document.getElementById('minThresholdSlider0').value,document.getElementById('minThresholdSlider1').value];
    const maxThresholds = [document.getElementById('maxThresholdSlider0').value,document.getElementById('maxThresholdSlider1').value];
    drawHistogram(canvas, histogram, minThresholds, maxThresholds);
}

function drawEntropyHistogram() {
    // Assuming originalEntropyImageData is already populated
    if (!originalEntropyImageData) return;

    const canvas = document.getElementById('entropyHistogramCanvas');
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    const data = originalEntropyImageData.data;
    let histogram = new Array(256).fill(0);
    for (let i = 0; i < data.length; i += 4) {
        const value = data[i];
        histogram[value]++;
    }

    const minThreshold = [document.getElementById('entropyMinThresholdSlider').value];
    const maxThreshold = [document.getElementById('entropyMaxThresholdSlider').value];
    drawHistogram(canvas, histogram, minThreshold, maxThreshold);
}

function drawHistogram(canvas, histogram, minThreshold, maxThreshold) {
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    const maxHistogramValue = Math.max(...histogram);
    histogram = histogram.map(v => (v / maxHistogramValue) * height);

    const barWidth = width / histogram.length;

    let start = 0; 
    let end = histogram.length;
    for (let k = 0; k < minThreshold.length; k++) {
        if (k === 0) {
            start = 0;
            end = maxThreshold[k];
            if (k === minThreshold.length - 1) {
            end = histogram.length;
            }
        } 
        if (k === minThreshold.length - 1 && k > 0) {
            start = maxThreshold[k - 1];
            end = histogram.length;
        } else if (k > 0) {
            start = maxThreshold[k - 1];
            end = maxThreshold[k];
        }
        for (let i = start; i < end; i++) {
            ctx.beginPath();
            ctx.rect(i * barWidth, height - histogram[i], barWidth, histogram[i]);
            ctx.fillStyle = (i >= minThreshold[k] && i <= maxThreshold[k]) ? 'red' : 'black';
            ctx.fill();
        }
    }
}



function magnify(imgID, zoom) {
    var img, glass, w, h, bw;
    img = document.getElementById(imgID);
    glass = document.createElement("DIV");
    glass.setAttribute("class", "img-magnifier-glass");
    img.parentElement.insertBefore(glass, img);
    
    // Setup the properties for the magnifying glass
    if (img.tagName === 'CANVAS') {
        glass.style.backgroundImage = "url('" + img.toDataURL() + "')";        
    } else {
        // for image
        glass.style.backgroundImage = "url('" + img.src + "')";
    }
    glass.style.backgroundRepeat = "no-repeat";
    glass.style.backgroundSize = (img.clientWidth * zoom) + "px " + (img.clientHeight * zoom) + "px";
    bw = 3;
    w = glass.offsetWidth / 2;
    h = glass.offsetHeight / 2;
    
    // Function to move the magnifier glass with the mouse
    function moveMagnifier(e) {
        var pos, x, y;
        e.preventDefault();
        pos = getCursorPos(e);
        x = pos.x;
        y = pos.y;

        // Update the position of the magnifier glass
        glass.style.left = (x - w) + "px";
        glass.style.top = (y - h) + "px";
        // Set the background position of the magnifier glass
        glass.style.backgroundPosition = "-" + ((x * zoom) - w + bw) + "px -" + ((y * zoom) - h + bw) + "px";
    }
    
    function getCursorPos(e) {
        var a, x = 0, y = 0;
        e = e || window.event;
        a = img.getBoundingClientRect();
        x = e.pageX - a.left - window.pageXOffset;
        y = e.pageY - a.top - window.pageYOffset;

        // since the canvas adjust its size to the screen, we need to scale the cursor position
        return {x : x, y : y};
    }
    
    
    // Add event listeners for moving and hiding the magnifier glass
    img.addEventListener("mousemove", moveMagnifier);
    glass.addEventListener("mousemove", moveMagnifier);
    
    // Improved handling for hiding the magnifying glass
    // Apply 'mouseleave' event to both image and glass
    img.addEventListener("mouseleave", function() {
        glass.style.visibility = 'hidden';
    });
    glass.addEventListener("mouseleave", function() {
        glass.style.visibility = 'hidden';
    });

    // Optional: Show the glass when entering the image area
    img.addEventListener("mouseenter", function() {
        glass.style.visibility = 'visible';
    });

    img.addEventListener("mouseenter", function() {
        glass.style.visibility = 'visible';
    });

    img.addEventListener("mousemove", moveMagnifier);
}

function removeMagnifier(imgID) {
    var img = document.getElementById(imgID);
    var glass = img.parentElement.getElementsByClassName('img-magnifier-glass')[0];
    if (glass) {
        glass.remove();
    }
}

function redrawCanvases() {
    getImageType()
    uploadedEntropyImage.src = uploadedEntropyImage.src;
}

function activateExperiment() {
    return new Promise((resolve, reject) => {
        // TODO: Control this function
        const uniqueQuery = '?nocache=' + new Date().getTime();
        fetch('/activate-experiment' + uniqueQuery, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                resolve();
            } else {
                reject();
            }
        })
        .catch(error => {
            console.error('Error:', error);
            reject();
        });
    }
    );
}

function deactivateCurrentExperiment() {
    return new Promise((resolve, reject) => {
        fetch('is-experiment-active', { method: 'GET' })
        .then(response => response.json())
        .then(data => {
            if (data.active === false) {
                resolve();
            } else {
                return fetch('/deactivate-experiment/' + String(data.experimentId), { method: 'POST' });
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                resolve();
            } else {
                reject();
            }
        })
        .catch(error => {
            console.error('Error:', error);
            reject();
        });
    });
}

function createIntensityHistogram() {
    return new Promise((resolve, reject) => {
        var img = new Image();
        img.onload = function() {
            var canvas = document.createElement('canvas');
            var ctx = canvas.getContext('2d');
            canvas.width = img.width;
            canvas.height = img.height;
            ctx.drawImage(img, 0, 0);
            
            grayscaleImageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
            drawIntensityHistogram(); // Draw the histogram using the fetched grayscale data
            resolve();
        };
        img.onerror = reject;
        img.src = uploadedImageURL_gray_blur;
    });
}

function loadExperiment(id) {
    displayWorkingMessage();
    fetch('/load-experiment/' + String(id), { method: 'GET' })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'error') {
            alert('No experiment data found.');
            removeWorkingMessage();
            return;
        } 
        // set the sliders and input boxes to the values from the experiment
        document.getElementById('minThresholdSlider0').value = data.minThreshold0;
        document.getElementById('minThresholdValue0').value = data.minThreshold0;
        document.getElementById('maxThresholdSlider0').value = data.maxThreshold0;
        document.getElementById('maxThresholdValue0').value = data.maxThreshold0;
        document.getElementById('minThresholdSlider1').value = data.minThreshold1;
        document.getElementById('minThresholdValue1').value = data.minThreshold1;
        document.getElementById('maxThresholdSlider1').value = data.maxThreshold1;
        document.getElementById('maxThresholdValue1').value = data.maxThreshold1;
        document.getElementById('entropyMinThresholdSlider').value = data.entropyMinThreshold;
        document.getElementById('entropyMinThresholdValue').value = data.entropyMinThreshold;
        document.getElementById('entropyMaxThresholdSlider').value = data.entropyMaxThreshold;
        document.getElementById('entropyMaxThresholdValue').value = data.entropyMaxThreshold;
        // set the blur slider and input box to the value from the experiment
        document.getElementById('blurSlider').value = data.blurValue;
        document.getElementById('blurValue').value = data.blurValue;
        if (data.expertGuess !== 'NaN') {
            document.getElementById('expertGuess').value = data.expertGuess;    
        }
        document.getElementById('info').value = data.info;

        uploadedImageURL_color = URL.createObjectURL(base64toBlob(data.color, 'image/png'));
        uploadedImageURL_gray = URL.createObjectURL(base64toBlob(data.gray, 'image/png'));
        uploadedImageURL_nobg = URL.createObjectURL(base64toBlob(data.nobg, 'image/png'));
        uploadedImageURL_color_blur = URL.createObjectURL(base64toBlob(data.color_blur, 'image/png'));
        uploadedImageURL_gray_blur = URL.createObjectURL(base64toBlob(data.gray_blur, 'image/png'));
        uploadedImageURL_nobg_blur = URL.createObjectURL(base64toBlob(data.nobg_blur, 'image/png'));

    })
    .then(() => {
            createIntensityHistogram();
        })
    .then(() => {document.getElementById('defaultImage').style.display = 'none';})
    .then(() => fetchOriginalEntropyData())
    .then(() => processImage())
    .then(() => processEntropyImage())
    .then(() => getImageType())
    .then(() => enableControls()) // Enable controls after everything is loaded
    .catch(error => {
        console.error('Error:', error);
    })
    .finally(() => removeWorkingMessage());
}

// Global event listeners
document.getElementById('sharpnessCheckbox').addEventListener('change', changeSharpness);  
document.getElementById('redOverlayCheckbox').addEventListener('change', changeRedOverlay);
document.getElementById('imageType').addEventListener('change', redrawCanvases); 
document.getElementById('index_evaluation').addEventListener('click', async function() { 
    if (document.getElementById('expertGuess').value === '') {
            alert('Please fill the expert guess field before evaluating the experiment.');
            return;
    } else {
    const uniqueQuery = '?nocache=' + new Date().getTime();
    console.log('Evaluating the experiment...');
    fetch('/evaluate-asphalt' + uniqueQuery, { method: 'POST' })
    .then(response => response.json())
    .then(response => {
        // display only 2 decimal places;
        let displayNum = response.evaluation*100;
        displayNum = displayNum.toFixed(2);
        alert('Evaluation completed. Check the console for the results.' + '\n' + 'Evaluation results: ' + displayNum + '%');
        }
    )
    .then(() => deactivateCurrentExperiment())
    .then(() => {
        // redirect to the '/' page
        window.location.href = '/';})
    }
});
// window.addEventListener('resize', function() { magnify('imageCanvas', 4); }); // this ensures the magnifying glass is redrawn when the window is resized
window.addEventListener('resize', redrawCanvases ); // this ensures the magnifying glass is redrawn when the window is resized

// when the user leaves the expertGuess field and the value is not empty, the min and max values will be updated
document.getElementById('expertGuess').addEventListener('change', function() {
    let value = this.value;
    if (value !== '') {
        // convert to number
        value = Number(value);
        if (value<0) {
            this.value = 0;
        } else if (value>100) {
            this.value =100;
        }
        value = this.value;
        // send the value to the server
        var  formData = new FormData();
        formData.append('expert_guess', value/100);
        const uniqueQuery = '?nocache=' + new Date().getTime();
        fetch('/update_value/expert_guess' + uniqueQuery, { method: 'POST', body: formData })
    }
});

// if the user visits the page '/' and the experiment is active, load the experiment
document.addEventListener('DOMContentLoaded', function() {
    fetch('/is-experiment-active')
    .then(response => response.json())
    .then(data => {
        if (data.active === true) {
            console.log('Experiment is active. Loading experiment data...', data.experimentId);
            loadExperiment(data.experimentId);
        }
    });
});


// keyboard shortcuts
document.addEventListener('keydown', function(event) {
    const eventKey = event.key.toLowerCase();
    switch (eventKey) {
        case 'a':
            document.getElementById('redOverlayCheckbox').checked = !document.getElementById('redOverlayCheckbox').checked;
            changeRedOverlay();
            break;
        case 'b':
            document.getElementById('sharpnessCheckbox').checked = !document.getElementById('sharpnessCheckbox').checked;
            changeSharpness();
            break;
        case 'c':
            let imageType = document.getElementById('imageType');
            imageType.selectedIndex = (imageType.selectedIndex + 1) % imageType.options.length;
            redrawCanvases();
            break;
        // case 's':
        //     // const uniqueQuery = '?nocache=' + new Date().getTime();
        //     // fetch('/save' + uniqueQuery, { method: 'POST' })
        //     fetch('/save', { method: 'POST' })
        //     break;
    }
});


// import OpenSeadragon from "./openseadragon_5.0/openseadragon.min.js";

let pointHistory = [];
let waitingForApproval = false;

// allocate the urls for the masks bg, aggregate, and asphalt
let mask_bg = null;
let mask_aggregate = null;
let mask_asphalt = null;
let displayed_mask = null;

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

const imageMaskBg = new Image();
const imageMaskAsphalt = new Image();
const imageMaskAggregate = new Image();
        
const labelSettings = {
  background: { stroke: 'green', fill: 'rgba(0,255,0,0.2)', strokeWidth: 2 },
  aggregate: { stroke: 'blue', fill: 'rgba(0,0,255,0.2)', strokeWidth: 2 },
  asphalt: { stroke: 'red', fill: 'rgba(255,0,0,0.2)', strokeWidth: 2 } 
};
function setMaskFilter (kl, img, rgba) {
  let konvaImage= new Konva.Image({
    x: 0,
    y: 0,
    image: img,
    width: document.getElementById('viewer').clientWidth,
    height: document.getElementById('viewer').clientHeight
  });
  konvaImage.cache();
  konvaImage.filters([Konva.Filters.RGBA]);
  konvaImage.red(rgba[0]);
  konvaImage.green(rgba[1]);
  konvaImage.blue(rgba[2]);
  konvaImage.alpha(rgba[3]);
  
  konvaStage.add(kl);
  kl.destroyChildren();
  kl.add(konvaImage);

}

imageMaskBg.onload = function() {
  //const rgba = labelSettings.background.fill.match(/\d+/g).map(Number);
  let rgba = labelSettings.background.fill.match(/[\d.]+/g).map(Number);
  rgba[3] = 1;
  console.log(rgba);
  setMaskFilter(konvaLayerMaskBg, imageMaskBg, rgba);
};
imageMaskAsphalt.onload = function() {
  let rgba = labelSettings.asphalt.fill.match(/[\d.]+/g).map(Number);
  rgba[3] = 1;
  console.log(rgba);
  setMaskFilter(konvaLayerMaskAsphalt, imageMaskAsphalt, rgba);
};
imageMaskAggregate.onload = function() {
  let rgba = labelSettings.aggregate.fill.match(/[\d.]+/g).map(Number);
  rgba[3] = 1;
  console.log(rgba);
  setMaskFilter(konvaLayerMaskAggregate,imageMaskAggregate, rgba);
};



// Draw polygons, rectangles, ellipses based on active tool
let activeTool = 'polygon';  // Default tool
let activeLabel = 'background';
let startPoint = null;  // Track the start point of the shape
let currentShape = null;

  
  function flattenPoints(points) {
    return points.map(point => {
      return [point.x, point.y];
    }).flat();
  }

  // Helper to create and draw shapes
  function drawShape(points) {
    if (waitingForApproval) {
      return;
    }
    let shape;
    
    points = flattenPoints(points);
    
    switch (activeTool) {
      case 'polygon':
      shape = new Konva.Line({
        points: points,
        closed: true,
        fill: labelSettings[activeLabel].fill,
        stroke: labelSettings[activeLabel].stroke,
        strokeWidth: labelSettings[activeLabel].strokeWidth,
        lineJoin: 'round',
        draggable: true
      });
      break;
      case 'rectangle':
            const width = Math.abs(points[0] - points[2]);
            const height = Math.abs(points[1] - points[3]);
            const x = Math.min(points[0], points[2]);
            const y = Math.min(points[1], points[3]);
            shape = new Konva.Rect({
                x: x,
                y: y,
                width: width,
                height: height,
                fill: labelSettings[activeLabel].fill,
                stroke: labelSettings[activeLabel].stroke,
                strokeWidth: labelSettings[activeLabel].strokeWidth,
                draggable: true
                });
            break;
        case 'ellipse':
            if (points.length < 4) {
              return;
            }
            let x_center = (points[0]+points[2])/2;
            let y_center = (points[1]+points[3])/2;
            let x_radius = Math.abs(points[0] - points[2])/2;
            let y_radius = Math.abs(points[1] - points[3])/2;
            if (points.length==6) {
              y_radius = Math.abs(y_center - points[5]);
            }
              shape = new Konva.Ellipse({
                x: x_center,
                y: y_center,
                radius: {
                  x: x_radius,
                  y: y_radius,
                  },
                fill: labelSettings[activeLabel].fill,
                stroke: labelSettings[activeLabel].stroke,
                strokeWidth: labelSettings[activeLabel].strokeWidth,
                draggable: true
              });
            break;
            }
            
            konvaLayer.add(shape);
            konvaLayer.draw();
            return shape;
}

function getImagePoint(position) {
  const viewportPoint = viewer.viewport.pointFromPixel(position);
  return viewer.viewport.viewportToImageCoordinates(viewportPoint);
}

function cancelAnnotation() {
  pointHistory = [];
  setTimeout(() => {
    konvaLayer.destroyChildren();
  }, 100);
}

function initializeMask() {
  fetch('/get-corrected-mask', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({})
  }).then(response => response.json())
    .then(data => {
      console.log('Mask data:', data);
      mask_bg = URL.createObjectURL(base64toBlob(data.bg, 'image/png'));
      mask_aggregate = URL.createObjectURL(base64toBlob(data.aggregate, 'image/png'));
      mask_asphalt = URL.createObjectURL(base64toBlob(data.asphalt, 'image/png'));

      imageMaskBg.src = mask_bg;
      imageMaskAsphalt.src = mask_asphalt;
      imageMaskAggregate.src = mask_aggregate;
    })
    .catch(error => {
      console.error('Error initializing mask:', error);
    });
}

function saveAnnotation() {
  // Save the annotation data to a server
  const annotationData = {
    label: activeLabel,
    shape: {
      type: activeTool,
      points: flattenPoints(pointHistory)
    }
  };

  fetch('/save-annotation', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(annotationData)
  }).then(response => response.json())
    .then(data => {
      mask_bg = URL.createObjectURL(base64toBlob(data.bg, 'image/png'));
      mask_aggregate = URL.createObjectURL(base64toBlob(data.aggregate, 'image/png'));
      mask_asphalt = URL.createObjectURL(base64toBlob(data.asphalt, 'image/png'));
      
      imageMaskBg.src = mask_bg;
      imageMaskAsphalt.src = mask_asphalt;
      imageMaskAggregate.src = mask_aggregate;
      
      /*
      let canvas = document.getElementById('viewerMaskCanvas');
      image.onload = function() {
        console.log('Image loaded:', image);
        canvas.width = image.width;
        canvas.height = image.height;
        canvas.getContext('2d').drawImage(image, 0, 0);
      };
      console.log(mask_bg);
      image.src = mask_aggregate;
      */

      console.log('Annotation saved:', data);
    })
    .catch(error => {
      console.error('Error saving annotation:', error);
    });

  // clean out the annotation
  pointHistory = [];
  setTimeout(() => {
    konvaLayer.destroyChildren();
  }, 200);
}

// Click event to handle shape drawing
viewer.addHandler('canvas-click', function (event) {
  if (waitingForApproval) {
    return;
  }
  const imagePoint = getImagePoint(event.position);
  
  pointHistory.push({ x: imagePoint.x, y: imagePoint.y });
  if (pointHistory.length==1) {
    startPoint = pointHistory[0];
    isDrawing = true;
  }
  
  if (pointHistory.length > 1) {
    if (currentShape) {
      currentShape.destroy();
    }
    switch (activeTool) {
      case 'rectangle':
          currentShape=drawShape(pointHistory);
          startPoint = null;  // Reset after drawing
          isDrawing = false; 
          waitingForApproval = true;
          break;
      case 'polygon':
          currentShape=drawShape(pointHistory);
          break;
      case 'ellipse':
          if (pointHistory.length==3) {
            currentShape=drawShape(pointHistory);
            startPoint = null;  // Reset after drawing
            isDrawing = false; 
            waitingForApproval = true;
            break;
          }
      break;

    }
  }
});

// Handle Enter key to finish the shape
document.addEventListener('keydown', function (event) {
  if (event.key === 'Enter' ) {
    if (waitingForApproval) {
      saveAnnotation();
      waitingForApproval = false;
    } else if (activeTool === 'polygon' && startPoint) {
      // Finish the polygon by connecting the last point to the first point
      konvaLayer.destroyChildren();
      pointHistory.push(startPoint);
      drawShape(pointHistory);
      startPoint = null;  // Reset after finishing the shape
      isDrawing = false;
      waitingForApproval = true;
    }
  }
  if (event.key === 'Escape') {
    // Cancel the current shape drawing
    currentShape.destroy();
    konvaLayer.batchDraw();
    startPoint = null;
    isDrawing = false;
    pointHistory = [];
    if (waitingForApproval) {
      cancelAnnotation();
      waitingForApproval = false;
    }
  }
});

// Button Click Handlers for Tool Switching
document.getElementById('polygon-btn').addEventListener('click', function () {
    activeTool = 'polygon';
    updateActiveButton('polygon-btn');
});

document.getElementById('rectangle-btn').addEventListener('click', function () {
  activeTool = 'rectangle';
  updateActiveButton('rectangle-btn');
  });
  
  document.getElementById('ellipse-btn').addEventListener('click', function () {
    activeTool = 'ellipse';
    updateActiveButton('ellipse-btn');
    });
    
document.getElementById('bgButton').addEventListener('click', () => {
// Button Click Handlers for Labeling
    const currentSettings = labelSettings['background'];
    activeLabel = 'background';
    const activeStroke = currentSettings.stroke;
    const activeFill = currentSettings.fill;
});

document.getElementById('fgButton').addEventListener('click', () => {
    activeLabel = 'aggregate';
    });
    
document.getElementById('asphaltButton').addEventListener('click', () => {
      activeLabel = 'asphalt';
});

// Helper to activate a tool
function updateActiveButton(activeBtnId) {
  var buttons = document.querySelectorAll('.tool-btn');
  buttons.forEach(button => button.classList.remove('active'));
  document.getElementById(activeBtnId).classList.add('active');
  } 


viewer.addHandler('viewport-change', function() {
const zoom = viewer.viewport.getZoom();  // Get current zoom level from OpenSeadragon

// Set scale for the Konva stage based on OpenSeadragon zoom level
konvaStage.scale({ x: zoom, y: zoom });

// Get the center of the OSD viewport (in viewport coordinates)
const center = viewer.viewport.getCenter();

// Convert OpenSeadragon center point (viewport coordinates) to Konva coordinates
const imageCenter = viewer.viewport.viewportToImageCoordinates(center.x, center.y);

// Adjust Konva stage position to match OSD viewport panning
konvaStage.position({
  x: -imageCenter.x * zoom + konvaStage.width() / 2,
  y: -imageCenter.y * zoom + konvaStage.height() / 2
});

// Redraw the Konva layer efficiently after transformations
konvaLayer.batchDraw();
});

// // Trigger initial sync
// viewer.viewport.zoomTo(1);
// viewer.viewport.panTo(new OpenSeadragon.Point(0, 0));
// konvaStage.scale({ x: 1, y: 1 });


function drawPreview(imagePoint) {    
if (currentShape) {
currentShape.destroy();
konvaLayer.batchDraw();
}
const pointSuggestions = pointHistory.concat({ x: imagePoint.x, y: imagePoint.y });
currentShape = drawShape(pointSuggestions);
}

// Event handler for starting to draw
addEventListener('mousemove', function (e) {
if (isDrawing) {
const offset = viewer.container.getBoundingClientRect();
const position = new OpenSeadragon.Point(e.clientX-offset.left, e.clientY-offset.top);
const imagePoint = getImagePoint(position);
drawPreview(imagePoint);
}
});


function adjustViewerSize() {
    const viewerBox = document.getElementById("viewer_box");
    const viewer = document.getElementById("viewer");
    const konvaLayer = document.getElementById("viewer_konva");

    // Set viewer and Konva layer width dynamically
    const newWidth = viewerBox.clientWidth;
    
    viewer.style.width = `${newWidth}px`;
    konvaLayer.style.width = `${newWidth}px`;
}

// Run on load and resize
window.addEventListener("resize", adjustViewerSize);
window.addEventListener("load", adjustViewerSize);