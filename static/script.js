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

document.getElementById('blurSlider').addEventListener('change', function() {
    document.getElementById('blurValue').value = this.value;
    blurImage(this.value);
});

function uploadImage() {
    document.getElementById('blurSlider').value = 0;
    document.getElementById('blurValue').value = 0;
    const fileInput = document.getElementById('fileInput');
    if (fileInput.files.length === 0) return;
    const file = fileInput.files[0];

    var formData = new FormData();
    formData.append('file', file);

    const uniqueQuery = '?nocache=' + new Date().getTime();

    // Fetch grayscale data and wait for it to complete
    fetch('/grayscale-data' + uniqueQuery, { method: 'POST', body: formData })
    .then(response => response.blob())
    .then(blob => {
        var url = URL.createObjectURL(blob);
        var img = new Image();
        return new Promise((resolve, reject) => {
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
        });
    })
    .then(() => fetchOriginalEntropyData())
    .then(() => processImage())
    .then(() => processEntropyImage())
    .then(() => {
        enableControls(); // Enable controls after everything is loaded
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
        fetch('/apply-mask' + uniqueQuery, { method: 'POST', body: formData })
        .then(response => response.blob())
        .then(imageBlob => {
            var imageUrl = URL.createObjectURL(imageBlob);
            var uploadedImage = document.getElementById('uploadedImage');
            uploadedImage.onload = function() {
                document.getElementById('defaultImage').style.display = 'none';
                uploadedImage.style.display = 'block';
                magnify("uploadedImage", 3);
                resolve(); // Resolve the promise when the image is loaded
            };
            uploadedImage.onerror = reject; // Reject the promise on error
            uploadedImage.src = imageUrl;
        })
        .catch(error => {
            console.error('Error:', error);
            reject(error); // Reject the promise on fetch error
        });
    });
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
            var ctx = canvas.getContext('2d');
            var img = new Image();
            img.onload = function() {
                canvas.width = img.width;
                canvas.height = img.height;
                ctx.drawImage(img, 0, 0);

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

function blurImage(blurValue) {
    var formData = new FormData();
    formData.append('blurValue', blurValue);
    const uniqueQuery = '?nocache=' + new Date().getTime();
    fetch('/blur' + uniqueQuery, { method: 'POST', body: formData })
    .then(response => response.blob())
    .then(blob => {
        var url = URL.createObjectURL(blob);
        var img = new Image();
        return new Promise((resolve, reject) => {
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
        });
    })
    .then(() => fetchOriginalEntropyData())
    .then(() => processImage())
    .then(() => processEntropyImage())
    .then(() => {
        enableControls(); // Enable controls after everything is loaded
    });
}

function validateAndUpdate() {
    processImage();
    processEntropyImage();
    drawEntropyHistogram();
    drawIntensityHistogram();
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

