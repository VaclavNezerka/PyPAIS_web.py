// global variables
let uploadedImageURL_color = null;
let uploadedImageURL_gray = null;
let uploadedImageURL_nobg = null;

let uploadedImageURL_color_blur = null;
let uploadedImageURL_gray_blur = null;
let uploadedImageURL_nobg_blur = null;

let requestedImage = null;
let displayImageBlur = false; 

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

// These listeners only update the mask, not the histogram
document.getElementById('minThresholdSlider').addEventListener('change', function() {
    let minVal = parseInt(this.value);
    let maxVal = parseInt(document.getElementById('maxThresholdSlider').value);
    if (minVal > maxVal) {
        document.getElementById('maxThresholdSlider').value = minVal;
        document.getElementById('maxThresholdValue').value = minVal;
    }
    document.getElementById('minThresholdValue').value = minVal;
    validateAndUpdate();
});
document.getElementById('minThresholdValue').addEventListener('change', function() {
    let minVal = Math.max(0, Math.min(255, parseInt(this.value)));
    let maxVal = parseInt(document.getElementById('maxThresholdSlider').value);
    if (minVal > maxVal) {
        document.getElementById('maxThresholdSlider').value = minVal;
        document.getElementById('maxThresholdValue').value = minVal;
    }
    document.getElementById('minThresholdSlider').value = minVal;
    this.value = minVal; // Correct the value in case it was out of bounds
    validateAndUpdate();
});

document.getElementById('maxThresholdSlider').addEventListener('change', function() {
    let maxVal = parseInt(this.value);
    let minVal = parseInt(document.getElementById('minThresholdSlider').value);
    if (maxVal < minVal) {
        document.getElementById('minThresholdSlider').value = maxVal;
        document.getElementById('minThresholdValue').value = maxVal;
    }
    document.getElementById('maxThresholdValue').value = maxVal;
    validateAndUpdate();
});
document.getElementById('maxThresholdValue').addEventListener('change', function() {
    let maxVal = Math.max(0, Math.min(255, parseInt(this.value)));
    let minVal = parseInt(document.getElementById('minThresholdSlider').value);
    if (maxVal < minVal) {
        document.getElementById('minThresholdSlider').value = maxVal;
        document.getElementById('minThresholdValue').value = maxVal;
    }
    document.getElementById('maxThresholdSlider').value = maxVal;
    this.value = maxVal; // Correct the value in case it was out of bounds
    validateAndUpdate();
});

// Event listeners for entropy min threshold slider and value
document.getElementById('entropyMinThresholdSlider').addEventListener('change', function() {
    let minVal = parseInt(this.value);
    let maxVal = parseInt(document.getElementById('entropyMaxThresholdSlider').value);
    if (minVal > maxVal) {
        document.getElementById('entropyMaxThresholdSlider').value = minVal;
        document.getElementById('entropyMaxThresholdValue').value = minVal;
    }
    document.getElementById('entropyMinThresholdValue').value = minVal;
    validateAndUpdate(); // Update the entropy image mask
});

document.getElementById('entropyMinThresholdValue').addEventListener('change', function() {
    let minVal = Math.max(0, Math.min(255, parseInt(this.value)));
    let maxVal = parseInt(document.getElementById('entropyMaxThresholdSlider').value);
    if (minVal > maxVal) {
        document.getElementById('entropyMaxThresholdSlider').value = minVal;
        document.getElementById('entropyMaxThresholdValue').value = minVal;
    }
    document.getElementById('entropyMinThresholdSlider').value = minVal;
    this.value = minVal; // Correct the value in case it was out of bounds
    validateAndUpdate(); // Update the entropy image mask
});

// Event listeners for entropy max threshold slider and value
document.getElementById('entropyMaxThresholdSlider').addEventListener('change', function() {
    let maxVal = parseInt(this.value);
    let minVal = parseInt(document.getElementById('entropyMinThresholdSlider').value);
    if (maxVal < minVal) {
        document.getElementById('entropyMinThresholdSlider').value = maxVal;
        document.getElementById('entropyMinThresholdValue').value = maxVal;
    }
    document.getElementById('entropyMaxThresholdValue').value = maxVal;
    validateAndUpdate(); // Update the entropy image mask
});

document.getElementById('entropyMaxThresholdValue').addEventListener('change', function() {
    let maxVal = Math.max(0, Math.min(255, parseInt(this.value)));
    let minVal = parseInt(document.getElementById('entropyMinThresholdSlider').value);
    if (maxVal < minVal) {
        document.getElementById('entropyMinThresholdSlider').value = maxVal;
        document.getElementById('entropyMinThresholdValue').value = maxVal;
    }
    document.getElementById('entropyMaxThresholdSlider').value = maxVal;
    this.value = maxVal; // Correct the value in case it was out of bounds
    validateAndUpdate(); // Update the entropy image mask
});

document.getElementById('blurValue').addEventListener('change', function() {
    let admissibleVal = Math.max(0, Math.min(50, parseInt(this.value)));
    this.value = admissibleVal; // Correct the value in case it was out of bounds
    document.getElementById('blurSlider').value = this.value;
    document.getElementById('blurValue').value = this.value;
    blurImage(this.value);
});

document.getElementById('blurSlider').addEventListener('change', async function() {
    document.getElementById('blurValue').value = this.value;
    try {
        document.getElementById('blurValue').value = this.value;
        displayWorkingMessage();
        await blurImage(this.value);
    } catch (error) {
        console.error('An error occurred:', error);
    } finally {
        removeWorkingMessage();
    }
});


async function uploadImage() {
    console.log('upload image')

    displayWorkingMessage(document.getElementById('uploadedImage'));

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
    if (uploadedImageURL_color_blur == null) {
        uploadedImageURL_color_blur = url;
    }
    await removeBackground(formData)
    
    fetchGrayscaleData(formData)
    .then(() => fetchOriginalEntropyData())
    .then(() => processImage())
    .then(() => processEntropyImage())
    .then(() => {enableControls(); }) // Enable controls after everything is loaded
    .then(() => {removeWorkingMessage(document.getElementById('uploadedImage'));});
}

function removeBackground(formData) {
    return new Promise((resolve, reject) => {
        const uniqueQuery = '?nocache=' + new Date().getTime();
        fetch('/remove-background' + uniqueQuery, { method: 'POST', body: formData })
        .then(response => response.blob())
        .then(blob => {
            var url = URL.createObjectURL(blob);
            uploadedImageURL_nobg = url;
            if (uploadedImageURL_nobg_blur == null) {
                uploadedImageURL_nobg_blur = url;
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
            var url = URL.createObjectURL(blob);
            var img = new Image();
            uploadedImageURL_gray = url;
            if (uploadedImageURL_gray_blur == null) {
                uploadedImageURL_gray_blur = url;
            }
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
            img.src = url;
        })
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
        formData.append('minThreshold', document.getElementById('minThresholdSlider').value);
        formData.append('maxThreshold', document.getElementById('maxThresholdSlider').value);
        formData.append('entropyMinThreshold', document.getElementById('entropyMinThresholdSlider').value);
        formData.append('entropyMaxThreshold', document.getElementById('entropyMaxThresholdSlider').value);
        formData.append('imageId', 'gray');

        const uniqueQuery = '?nocache=' + new Date().getTime();
        fetch('/apply-mask'+uniqueQuery, { method: 'POST', body: formData })
        .then(response => response.blob())
        .then(imageBlob => {
            var imageUrl = URL.createObjectURL(imageBlob);
            var uploadedImage = document.getElementById('uploadedImage');
            uploadedImage.onload = function() {
                document.getElementById('defaultImage').style.display = 'none';
                uploadedImage.style.display = 'block';
                magnify("uploadedImage", 4);
                resolve(); // Resolve the promise when the image is loaded
            };
            uploadedImage.onerror = reject; // Reject the promise on error
            uploadedImage.src = getImageType()
        })
        .catch(error => {
            console.error('Error:', error);
            reject(error); // Reject the promise on fetch error
        });
    });
}


function changeSharpness() {
    console.log('change sharpness')
    displayImageBlur = !displayImageBlur;
    if (displayImageBlur) {
        document.getElementById('uploadedImage').src = uploadedImageURL_color_blur;
    }
    else {
        document.getElementById('uploadedImage').src = uploadedImageURL_color;
    }

}

function processEntropyImage() {
    return new Promise((resolve, reject) => {
        var formData = new FormData();
        formData.append('minThreshold', document.getElementById('minThresholdSlider').value);
        formData.append('maxThreshold', document.getElementById('maxThresholdSlider').value);
        formData.append('entropyMinThreshold', document.getElementById('entropyMinThresholdSlider').value);
        formData.append('entropyMaxThreshold', document.getElementById('entropyMaxThresholdSlider').value);
        formData.append('imageId', 'entropy');

        const uniqueQuery = '?nocache=' + new Date().getTime();
        fetch('/apply-mask' + uniqueQuery, { method: 'POST', body: formData })
        .then(response => response.blob())
        .then(blob => {
            var url = URL.createObjectURL(blob);
            var canvas = document.getElementById('entropyCanvas');
            var ctx = canvas.getContext('2d', { willReadFrequently: true });
            var img = new Image();
            img.onload = function() {
                canvas.width = img.width;
                canvas.height = img.height;
                ctx.drawImage(img, 0, 0);
                
                // This is used to determine if the user is reading the histogram frequently

                entropyImageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                drawEntropyHistogram();
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


function getImageType() {
    console.log('change image type')
    console.log(displayImageBlur)
    var imageType = document.getElementById('imageType').value;
    var uploadedImage = document.getElementById('uploadedImage');
    if (displayImageBlur) {
        switch (imageType) {
            case 'original':
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
    return uploadedImage.src;
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

// this function converts a base64 string to a blob
// the images are in a str64 format and it is decoded as a utf-8 string
// we need to convert them to a blob
function base64toBlob(base64, type) {
    var byteString = atob(base64);
    var ab = new ArrayBuffer(byteString.length);
    var ia = new Uint8Array(ab);
    for (var i = 0; i < byteString.length; i++) {
        ia[i] = byteString.charCodeAt(i);
    }
    return new Blob([ab], { type: type });
}


function blurImage(blurValue) {
    return new Promise((resolve, reject) => {
        console.log('blur image')
        var formData = new FormData();
        formData.append('blurValue', blurValue);
        const uniqueQuery = '?nocache=' + new Date().getTime();
        fetch('/blur' + uniqueQuery, { method: 'POST', body: formData })
        .then(response => {
        // the response is in a JSON format
        // the keys are color and gray and the values are the images
            return response.json();
        })
        .then(data => {            
            let color = data.color;
            let gray = data.gray;
            let nobg = data.nobg;
            
            try {
                // the images are in a str64 format and it is decoded as a utf-8 string
                // transfer it to blob
                
                // TODO // FIX THIS
                // the BE is not returning the images in the correct format the color should not have a bg removed
                // it should also return the image with the bg removed

                let colorBlob = base64toBlob(color, 'image/png');
                let grayBlob = base64toBlob(gray, 'image/png');
                // let nobgBlob = base64toBlob(nobg, 'image/png');
                uploadedImageURL_color_blur = URL.createObjectURL(colorBlob);
                uploadedImageURL_gray_blur = URL.createObjectURL(grayBlob);
                // uploadedImageURL_nobg_blur = URL.createObjectURL(nobgBlob);
            } catch (error) {
                console.error('An error occurred:', error);
            }
            
        })
        .catch(error => {
            reject(error);
            console.error('Error:', error);
        })           
        .then(() => fetchOriginalEntropyData())
        .then(() => processImage())
        .then(() => processEntropyImage())
        .then(() => {
            enableControls(); // Enable controls after everything is loaded
        }).then(() => {
            resolve();
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
    removeWorkingMessage();
}

function drawIntensityHistogram() {
    // Assuming grayscaleImageData is already populated
    if (!grayscaleImageData) return;

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
    drawHistogram(canvas, histogram, document.getElementById('minThresholdSlider').value, document.getElementById('maxThresholdSlider').value);
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

    drawHistogram(canvas, histogram, document.getElementById('entropyMinThresholdSlider').value, document.getElementById('entropyMaxThresholdSlider').value);
}

function drawHistogram(canvas, histogram, minThreshold, maxThreshold) {
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    const maxHistogramValue = Math.max(...histogram);
    histogram = histogram.map(v => (v / maxHistogramValue) * height);

    const barWidth = width / histogram.length;
    for (let i = 0; i < histogram.length; i++) {
        ctx.beginPath();
        ctx.rect(i * barWidth, height - histogram[i], barWidth, histogram[i]);
        ctx.fillStyle = (i >= minThreshold && i <= maxThreshold) ? 'red' : 'black';
        ctx.fill();
    }
}



function magnify(imgID, zoom) {
    var img, glass, w, h, bw;
    img = document.getElementById(imgID);
    glass = document.createElement("DIV");
    glass.setAttribute("class", "img-magnifier-glass");
    img.parentElement.insertBefore(glass, img);

    // Setup the properties for the magnifying glass
    glass.style.backgroundImage = "url('" + img.src + "')";
    glass.style.backgroundRepeat = "no-repeat";
    glass.style.backgroundSize = (img.width * zoom) + "px " + (img.height * zoom) + "px";
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

