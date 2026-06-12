window.addEventListener("load", () => {
    let streaming = false

    const video = document.getElementById("video")
    const canvas = document.getElementById("outputCanvas")
    const photo = document.getElementById("capturedImage")
    const startButton = document.getElementById("capture-photo-button")

    startButton.addEventListener("click", () => {
        navigator.mediaDevices
            .getUserMedia({ video: true, audio: false })
            .then((stream) => {
                video.srcObject = stream
                video.play()
            })
            .catch((err) => {
                console.error(`An error occurred: ${err}`)
            })
    })

    video.addEventListener("canplay", (ev) => {
        if (!streaming) {
            canvas.setAttribute("width", video.videoWidth)
            canvas.setAttribute("height", video.videoHeight)
            streaming = true
        }
    })

    startButton.addEventListener("click", (ev) => {
        takePicture()
        ev.preventDefault()
    })

    function clearPhoto() {
        const context = canvas.getContext("2d")
        context.fillStyle = "#aaaaaa"
        context.fillRect(0, 0, canvas.width, canvas.height)

        const data = canvas.toDataURL("image/png")
        photo.setAttribute("src", data)
    }

    function switchOffCamera() {
        const stream = video.srcObject
        if (stream) {
            const tracks = stream.getTracks()
            tracks.forEach((track) => track.stop())
            video.srcObject = null
            // switch off the camera and hide the captured image
            document.getElementById("capturedImageDiv").style.display = "none"
            // stop using the camera
            // document.mediaDevices.getUserMedia({ video: false, audio: false })
        }
    }

    clearPhoto()

    function takePicture() {
        const context = canvas.getContext("2d")
        if (video.videoWidth && video.videoHeight) {
            context.drawImage(video, 0, 0)

            const data = canvas.toDataURL("image/png")
            photo.setAttribute("src", data)

            canvas.toBlob((blob) => {
                const file = new File([blob], "photo.jpg", {
                    type: "image/jpeg",
                })

                // Create a DataTransfer to simulate file selection
                const dt = new DataTransfer()
                dt.items.add(file)

                const fileInput = document.getElementById("fileInput")
                fileInput.files = dt.files
            }, "image/jpeg")

            document.getElementById("upload-button-camera").disabled = false
        } else {
            clearPhoto()
        }
    }

    document.getElementById("upload-button-camera").disabled = true
    document
        .getElementById("upload-button-camera")
        .addEventListener("click", () => {
            switchOffCamera()
        })

    document
        .getElementById("take-photo-open-button")
        .addEventListener("click", () => {
            document.getElementById("capturedImageDiv").style.display = "flex"
        })
})

// function getDeviceType() {
//     if (navigator.userAgentData) {
//         return navigator.userAgentData.mobile ? "mobile" : "pc"
//     }

//     const isMobileUA = /Mobi|Android|iPhone|iPad|iPod/i.test(
//         navigator.userAgent,
//     )
//     const isSmallScreen = window.innerWidth <= 768

//     return isMobileUA || isSmallScreen ? "mobile" : "pc"
// }
