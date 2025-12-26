// this function converts a base64 string to a blob
// the images are in a str64 format and it is decoded as a utf-8 string
// we need to convert them to a blob
export default function base64toBlob(base64, type) {
    var byteString = atob(base64)
    var ab = new ArrayBuffer(byteString.length)
    var ia = new Uint8Array(ab)
    for (var i = 0; i < byteString.length; i++) {
        ia[i] = byteString.charCodeAt(i)
    }
    return new Blob([ab], { type: type })
}

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

export { hexToRgba, colorizeMask}
