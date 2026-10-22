/** Mode controls and the numeric control each one governs. */
const GROUPS = [
    ["whiteBalanceMode", "colorTemperature"],
    ["exposureMode", "exposureTime"],
    ["focusMode", "focusDistance"],
]
/** Numeric controls without a mode switch, in the order they are applied. */
const SINGLE_KEYS = [
    "iso",
    "exposureCompensation",
    "brightness",
    "contrast",
    "saturation",
    "sharpness",
    "zoom",
]
const MODE_KEYS = GROUPS.map((g) => g[0])
const NUMERIC_KEYS = [...GROUPS.map((g) => g[1]), ...SINGLE_KEYS]
/** Every control this module knows about. */
const CONTROL_KEYS = [
    ...MODE_KEYS,
    ...NUMERIC_KEYS,
    "width",
    "height",
    "frameRate",
    "deviceId",
]
const MODES = ["none", "manual", "single-shot", "continuous"]
const SYMBOLIC = ["min", "max", "mid", "current"]

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function pick(obj, keys) {
    const out = {}
    for (const k of keys) if (obj && obj[k] !== undefined) out[k] = obj[k]
    return out
}

function isRange(cap) {
    return (
        !!cap &&
        typeof cap === "object" &&
        Number.isFinite(cap.min) &&
        Number.isFinite(cap.max)
    )
}

window.addEventListener("load", () => {
    let streaming = false

    const video = document.getElementById("video")
    const canvas = document.getElementById("outputCanvas")
    const photo = document.getElementById("capturedImage")
    const startButton = document.getElementById("capture-photo-button")

    startButton.addEventListener("click", () => {
        navigator.mediaDevices
            .getUserMedia({
                video: { width: { ideal: 5472 }, height: { ideal: 3648 } },
                audio: false,
            })
            .then(async (stream) => {
                video.srcObject = stream
                video.play()
                track = stream.getVideoTracks()[0]
                caps = await waitForControls(track)
                renderRows()
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
            unlockCamera(track)
            const tracks = stream.getTracks()
            tracks.forEach((track) => track.stop())
            video.srcObject = null
            // switch off the camera and hide the captured image
            document.getElementById("capturedImageDiv").style.display = "none"
            document.getElementById("manualSettingsDiv").style.display = "none"
            // stop using the camera
            document.mediaDevices.getUserMedia({
                video: { width: { ideal: 5472 }, height: { ideal: 3648 } },
                audio: false,
            })
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
            document.getElementById("manualSettingsDiv").style.display = "flex"
        })
})

//

const $ = (id) => document.getElementById(id)
const platform = detectPlatform()
let stream = null,
    track = null,
    caps = {},
    timer = null
let samples = []
const WINDOW_MS = 30000

// -----------------------------------------
// DEFINITIONS OF DEFAULT VALUES AND UI ROWS
// -----------------------------------------

const DEFAULT_PROFILE = {
    whiteBalanceMode: "manual",
    colorTemperature: 5000, // K
    exposureMode: "manual",
    exposureTime: 200, // 20 ms
    gain: "min", // Windows only
    iso: "min", // Android only
    brightness: "mid",
    contrast: "mid",
    saturation: "mid",
    sharpness: "mid",
    focusMode: "manual",
    focusDistance: "current",
}

const CURRENT_PROFILE = { ...DEFAULT_PROFILE }

const ROWS = [
    {
        key: "colorTemperature",
        mode: "whiteBalanceMode",
        name: "White balance",
        unit: "K",
    },
    {
        key: "exposureTime",
        mode: "exposureMode",
        name: "Exposure",
        unit: "ms",
        toUi: (v) => v / 10,
        fromUi: (v) => v * 10,
        log: true,
    },
    {
        key: "exposureCompensation",
        name: platform === "Windows" ? "Gain" : "Exposure bias",
        unit: platform === "Windows" ? "" : "auto mode only",
    },
    { key: "iso", name: "ISO", unit: "" },
    { key: "brightness", name: "Brightness", unit: "" },
    { key: "contrast", name: "Contrast", unit: "" },
    { key: "saturation", name: "Saturation", unit: "" },
    { key: "sharpness", name: "Sharpness", unit: "" },
    { key: "focusDistance", mode: "focusMode", name: "Focus", unit: "" },
    { key: "zoom", name: "Zoom", unit: "" },
]

// $("manual-cam-settings").addEventListener("click", () => {
//     $("manual-cam-settings-div").hidden = false
//     renderRows()
// })

function renderRows() {
    const rows = $("manual-rows")
    rows.replaceChildren()

    const missing = []
    for (const r of ROWS) {
        const caption = caps[r.key]
        const modes = r.mode ? caps[r.mode] : null

        if (!isRange(caption) && !Array.isArray(modes)) {
            missing.push(r.name)
            continue
        }

        const row = document.createElement("div")
        row.className = "row-manual"
        row.dataset.key = r.key
        const id = `in-${r.key}`
        // row.innerHTML = `<label class="modern-label" for="${id}">${r.name}${r.unit ? ` <span class="modern-label">${r.unit}</span>` : ""}</label>`
        row.innerHTML = `<label class="modern-label" for="${id}">${r.name}${r.unit ? ` [${r.unit}]` : ""}</label>`

        if (Array.isArray(modes)) {
            const sel = document.createElement("select")
            sel.classList.add("enhanced-select")
            sel.setAttribute("aria-label", `${r.name} mode`)
            for (const m of modes)
                sel.append(
                    new Option(m === "continuous" ? "auto (continuous)" : m, m),
                )
            sel.addEventListener("change", () => setMode(r, sel.value))
            row.append(sel)
        } else {
            const span = document.createElement("span")
            span.className = "text-gray-500"
            span.textContent = "no auto mode"

            row.append(span)
        }
        if (isRange(caption)) {
            const toUi = r.toUi || ((x) => x),
                fromUi = r.fromUi || ((x) => x)
            const range = document.createElement("input")
            range.className = "slider"
            range.type = "range"

            //             <div class="slider-group">
            //     <input type="range" id="opacitySlider" min="0" max="100" value="50" class="slider">
            //     <input type="text" id="opacityValue" value="50" size="2" class="enhanced-input">
            // </div>
            range.setAttribute("aria-label", `${r.name} slider`)
            if (r.log) {
                range.min = Math.log2(caption.min)
                range.max = Math.log2(caption.max)
                range.step = 0.001
            } else {
                range.min = caption.min
                range.max = caption.max
                range.step = caption.step > 0 ? caption.step : "any"
            }
            const num = document.createElement("input")
            num.type = "number"
            num.id = id
            num.min = toUi(caption.min)
            num.max = toUi(caption.max)
            num.step = "any"
            range.addEventListener("input", () => {
                num.value = fmt(toUi(r.log ? 2 ** range.value : +range.value))
                // adjust current profile
                CURRENT_PROFILE[r.key] = r.log ? 2 ** range.value : +range.value
            })
            range.addEventListener(
                "change",
                () => setValue(r, r.log ? 2 ** range.value : +range.value),
                // adjust current profile
                (CURRENT_PROFILE[r.key] = r.log
                    ? 2 ** range.value
                    : +range.value),
            )
            num.addEventListener(
                "change",
                () => setValue(r, fromUi(+num.value)),
                // adjust current profile
                (CURRENT_PROFILE[r.key] = fromUi(+num.value)),
            )
            row.append(range, num)
        } else {
            row.append(
                document.createElement("span"),
                document.createElement("span"),
            )
        }
        const held = document.createElement("div")
        held.className = "held"
        row.append(held)
        rows.append(row)
    }
    // $("missing").textContent = missing.length
    //     ? `Not exposed for this camera here: ${missing.join(", ")}.`
    //     : ""
    // $("hint").hidden = rows.childElementCount > 0
    applyProfile(CURRENT_PROFILE)
    refresh()
}

renderRows.onError = (e) => {
    console.error("renderRows error:", e)
}
async function apply(set, what) {
    try {
        await track.applyConstraints({ advanced: [set] })
    } catch (e) {
        console.error(`${what}: the camera refused it. ${describe(e)}`, true)
    }
    refresh()
}

function setValue(r, raw) {
    const set = { [r.key]: snapToCapability(r.key, raw, caps[r.key]) }
    // A value only takes effect in manual mode (Windows switches on the value itself).
    if (r.mode && caps[r.mode]?.includes("manual")) set[r.mode] = "manual"
    return apply(
        set,
        `${r.name} ${fmt((r.toUi || ((x) => x))(set[r.key]))}${r.unit && r.unit !== "auto mode only" ? ` ${r.unit}` : ""}`,
    )
}

function setMode(r, mode) {
    const set = { [r.mode]: mode }
    const v = track.getSettings()[r.key]
    if (mode === "manual" && isRange(caps[r.key]) && Number.isFinite(v))
        set[r.key] = snapToCapability(r.key, v, caps[r.key])
    return apply(set, `${r.name} mode ${mode}`)
}

function refresh() {
    if (!track) return
    const s = track.getSettings()
    console.log("Camera settings refreshed:", s)
    for (const row of $("manual-rows").children) {
        const r = ROWS.find((x) => x.key === row.dataset.key)
        const sel = row.querySelector("select"),
            range = row.querySelector("input[type=range]"),
            num = row.querySelector("input[type=number]")
        const v = s[r.key],
            toUi = r.toUi || ((x) => x)
        if (sel && s[r.mode]) sel.value = s[r.mode]
        if (range && Number.isFinite(v)) range.value = r.log ? Math.log2(v) : v
        if (num && document.activeElement !== num) num.value = fmt(toUi(v))
    }
}
refresh.onError = (e) => {
    console.error("refresh error:", e)
}

function applyProfile(profile) {
    lockCamera(track, profile, { platform })
    for (const r of ROWS) {
        if (!isRange(caps[r.key])) continue
        $(`in-${r.key}`).value = profile[r.key]
    }
}

function detectPlatform() {
    const nav = globalThis.navigator || {}
    const p = nav.userAgentData && nav.userAgentData.platform
    if (p) return p

    const ua = navigator.userAgent
    if (ua.includes("Windows")) return "Windows"
    if (ua.includes("Android")) return "Android"
    if (ua.includes("Linux")) return "Linux"
    if (ua.includes("Macintosh")) return "Mac"
    if (ua.includes("CrOS")) return "ChromeOS"
    if (ua.includes("iPhone") || ua.includes("iPad") || ua.includes("iPod"))
        return "iOS"
    return "Unknown"
}

// -----------------------------------------
// MANUAL CAMERA SETTINGS - FUNCTIONS
// -----------------------------------------

/**
 * Current Chromium already lists the camera controls in getCapabilities() when
 * getUserMedia() resolves (verified on Chromium 141); this polls briefly in case a
 * browser fills them in later. Returns the capabilities, possibly without any
 * camera controls (e.g. Firefox, where it waits the full timeout).
 */
async function waitForControls(track, timeoutMs = 3000) {
    if (typeof track.getCapabilities !== "function") return {}
    const t0 = Date.now()
    let caps = track.getCapabilities()
    while (
        !CONTROL_KEYS.some((k) => k in caps) &&
        track.readyState === "live" &&
        Date.now() - t0 < timeoutMs
    ) {
        await sleep(100)
        caps = track.getCapabilities()
    }
    return caps
}

/** Snapshot of the camera controls: { platform, label, capabilities, settings }. */
function readCameraControls(track, platform = detectPlatform()) {
    const caps =
        typeof track.getCapabilities === "function"
            ? track.getCapabilities()
            : {}

    // console.log('Camera settings:', track.getSettings());
    return {
        platform,
        label: track.label,
        capabilities: pick(caps, CONTROL_KEYS),
        settings: pick(track.getSettings(), CONTROL_KEYS),
    }
}

/**
 * Chromium on Windows converts exposureTime to DirectShow's log2-seconds control, so
 * the reachable values are 1e4·2^n (100 µs units) and the reported step is (2^s − 1)·min.
 * A requested value is truncated toward zero in log2 space (e.g. 200 → 312.5), so we
 * snap to the nearest power of two ourselves instead.
 */
function isLog2SecondsGrid(cap) {
    const isInt = (x) =>
        Number.isFinite(x) && Math.abs(x - Math.round(x)) < 1e-9
    return (
        cap.min > 0 &&
        cap.step > 0 &&
        isInt(Math.log2(cap.min / 1e4)) &&
        isInt(Math.log2(cap.max / 1e4)) &&
        isInt(Math.log2(cap.step / cap.min + 1))
    )
}

function clamp(x, lo, hi) {
    return Math.min(hi, Math.max(lo, x))
}

/** Clamp `value` to the capability range of control `key` and snap it to the camera's grid. */
function snapToCapability(key, value, cap) {
    let x = clamp(value, cap.min, cap.max)
    if (key === "exposureTime" && isLog2SecondsGrid(cap)) {
        return clamp(
            1e4 * 2 ** Math.round(Math.log2(x / 1e4)),
            cap.min,
            cap.max,
        )
    }
    if (cap.step > 0) {
        x = cap.min + Math.round((x - cap.min) / cap.step) * cap.step
        if (x > cap.max + 1e-9) x -= cap.step
        x = Number(clamp(x, cap.min, cap.max).toPrecision(12)) // drop floating-point noise
    }
    return x
}

function resolveTarget(key, target, cap, current) {
    let v
    if (typeof target === "number") v = target
    else if (target === "min") v = cap.min
    else if (target === "max") v = cap.max
    else if (target === "mid") v = (cap.min + cap.max) / 2
    else if (target === "current") v = current
    if (!Number.isFinite(v)) return undefined
    return snapToCapability(key, v, cap)
}

async function tryApply(track, constraintSet) {
    try {
        // Bare values in the first advanced set: the long-standing form for these
        // controls; Chromium treats them as exact there and rejects an unsupported or
        // out-of-range value instead of silently ignoring it.
        await track.applyConstraints({ advanced: [constraintSet] })
        return null
    } catch (e) {
        return `${e.name}${e.constraint ? ` (${e.constraint})` : ""}: ${e.message}`
    }
}

function validateTarget(key, value) {
    if (MODE_KEYS.includes(key)) {
        if (!MODES.includes(value))
            throw new TypeError(
                `${key}: expected one of ${MODES.join(", ")}, got ${JSON.stringify(value)}`,
            )
    } else if (
        !(typeof value === "number" && Number.isFinite(value)) &&
        !SYMBOLIC.includes(value)
    ) {
        throw new TypeError(
            `${key}: expected a number or one of ${SYMBOLIC.join(", ")}, got ${JSON.stringify(value)}`,
        )
    }
}

/**
 * Lock the camera behind `track` to `profile`.
 *
 * Each mode is sent together with its value (Windows switches to manual only when a
 * value arrives), every other control in a call of its own (on Windows a failing
 * property aborts the rest of its call). Afterwards every value is read back.
 *
 * @param {MediaStreamTrack} track  live video track from getUserMedia()
 * @param {object} profile
 * @param {object} [options]
 * @param {string} [options.platform]   override detectPlatform()
 * @param {number} [options.timeoutMs=3000]  how long to wait for the controls to appear
 * @param {boolean} [options.keepLocked=false]  re-apply the resolved values whenever
 *        the browser reports that something else changed the camera ('configurationchange')
 * @param {(report: object) => void} [options.onRelock]  called after each re-apply
 * @returns {Promise<{ok: boolean, platform: string, label: string, items: object[],
 *          settings: object, resolvedProfile: object, stopKeepingLocked?: () => void}>}
 *   `ok` is true only if every requested control is supported, accepted and reads back
 *   as sent. Each item: { key, requested, sent, effective, status, note } with status
 *   'ok' | 'mismatch' | 'unsupported' | 'error' | 'unverified'.
 */
async function lockCamera(track, profile, options = {}) {
    // console.log('lockCamera: requested profile:', track.getSettings(), profile);

    if (!track || track.kind !== "video")
        throw new TypeError("lockCamera: expected a video MediaStreamTrack")
    const platform = options.platform || detectPlatform()
    const caps = await waitForControls(track, options.timeoutMs ?? 3000)
    const items = []
    const item = (key, requested, extra = {}) => {
        const it = {
            key,
            requested,
            sent: undefined,
            effective: undefined,
            status: "pending",
            note: "",
            ...extra,
        }
        items.push(it)
        return it
    }

    // Validate and translate the profile.
    const target = {}
    for (const [key, value] of Object.entries(profile || {})) {
        if (value === undefined || value === null) continue
        if (key === "gain") {
            validateTarget("exposureCompensation", value)
            if (platform === "Windows") {
                if ("exposureCompensation" in profile)
                    throw new TypeError(
                        "Use 'gain' or 'exposureCompensation', not both: on Windows they are the same control.",
                    )
                target.exposureCompensation = value
            } else {
                item("gain", value, {
                    status: "unsupported",
                    note:
                        platform === "Android"
                            ? "use 'iso' on Android"
                            : "Chromium exposes camera gain only on Windows",
                })
            }
            continue
        }
        if (!CONTROL_KEYS.includes(key))
            throw new TypeError(
                `Unknown control '${key}'. Known: ${CONTROL_KEYS.join(", ")}, gain`,
            )
        validateTarget(key, value)
        target[key] = value
    }
    const label = (key) =>
        key === "exposureCompensation" && "gain" in (profile || {})
            ? "gain"
            : key

    // 1. Mode + value pairs: white balance, exposure, focus.
    for (const [modeKey, valueKey] of GROUPS) {
        if (!(modeKey in target) && !(valueKey in target)) continue
        const modeItem =
            modeKey in target ? item(modeKey, target[modeKey]) : null
        const valueItem =
            valueKey in target ? item(valueKey, target[valueKey]) : null
        const set = {}

        if (modeItem) {
            const offered = caps[modeKey]
            if (Array.isArray(offered) && offered.includes(target[modeKey]))
                set[modeKey] = target[modeKey]
            else {
                modeItem.status = "unsupported"
                modeItem.note = Array.isArray(offered)
                    ? `camera offers: ${offered.join(", ") || "nothing"}`
                    : "not exposed by this browser/camera"
            }
        }
        if (valueItem) {
            const cap = caps[valueKey]
            if (!isRange(cap)) {
                valueItem.status = "unsupported"
                valueItem.note = "not exposed by this browser/camera"
            } else {
                let current
                if (target[valueKey] === "current") {
                    // Switching the mode first makes Chromium re-read the device state
                    // before applyConstraints() resolves, so getSettings() is fresh.
                    if (set[modeKey] !== undefined) {
                        const err = await tryApply(track, {
                            [modeKey]: set[modeKey],
                        })
                        if (err)
                            valueItem.note = `mode switch before reading: ${err}`
                    }
                    current = track.getSettings()[valueKey]
                }
                const v = resolveTarget(
                    valueKey,
                    target[valueKey],
                    cap,
                    current,
                )
                if (v === undefined) {
                    valueItem.status = "unsupported"
                    valueItem.note = "camera reports no current value"
                } else set[valueKey] = v
            }
        }
        if (Object.keys(set).length === 0) continue
        if (modeItem && set[modeKey] !== undefined) modeItem.sent = set[modeKey]
        if (valueItem && set[valueKey] !== undefined)
            valueItem.sent = set[valueKey]
        const err = await tryApply(track, set)
        if (err)
            for (const it of [modeItem, valueItem])
                if (it && it.sent !== undefined) {
                    it.status = "error"
                    it.note = err
                }
    }

    // 2. Controls without a mode, one call each.
    for (const key of SINGLE_KEYS) {
        if (!(key in target)) continue
        const it = item(label(key), target[key], { control: key })
        const cap = caps[key]
        if (!isRange(cap)) {
            it.status = "unsupported"
            it.note =
                key === "iso"
                    ? "ISO is exposed only on Android"
                    : "not exposed by this browser/camera"
            continue
        }
        const v = resolveTarget(key, target[key], cap, track.getSettings()[key])
        if (v === undefined) {
            it.status = "unsupported"
            it.note = "camera reports no current value"
            continue
        }
        it.sent = v
        const err = await tryApply(track, { [key]: v })
        if (err) {
            it.status = "error"
            it.note = err
        }
    }

    // 3. Read everything back.
    const after = track.getSettings()
    for (const it of items) {
        const key = it.control || it.key
        const eff = after[key]
        if (it.status === "error") it.effective = eff // show what the camera holds anyway
        if (it.status !== "pending") continue
        it.effective = eff
        if (eff === undefined) {
            it.status = "unverified"
            it.note = "browser does not report this setting"
        } else if (typeof it.sent === "string") {
            it.status = eff === it.sent ? "ok" : "mismatch"
        } else {
            const cap = caps[key]
            const tol = Math.max(
                cap && cap.step > 0 ? cap.step / 2 : 0,
                1e-6 * Math.max(1, Math.abs(it.sent)),
            )
            it.status = Math.abs(eff - it.sent) <= tol ? "ok" : "mismatch"
        }
        if (it.status === "mismatch" && !it.note)
            it.note = "camera holds a different value than requested"
    }

    // Concrete values that were accepted — what to store, and what to re-apply on drift.
    const resolvedProfile = {}
    for (const it of items)
        if (it.status === "ok") resolvedProfile[it.key] = it.sent

    const report = {
        ok: items.length > 0 && items.every((it) => it.status === "ok"),
        platform,
        label: track.label,
        items,
        settings: pick(after, CONTROL_KEYS),
        resolvedProfile,
    }

    if (options.keepLocked)
        report.stopKeepingLocked = keepLocked(track, report, {
            ...options,
            platform,
        })
    return report
}

/**
 * Re-apply report.resolvedProfile whenever the browser reports (via the track's
 * 'configurationchange' event) that a locked control no longer holds the value it
 * held at lock time — e.g. vendor software or another app re-enabled auto white
 * balance. Chromium fires that event on Windows and Linux for changes made outside
 * the page; its own applyConstraints() calls do not trigger it.
 */
function keepLocked(track, report, options) {
    let busy = false
    const drifted = () => {
        const s = track.getSettings()
        return report.items.some((it) => {
            if (it.status !== "ok") return false
            const now = s[it.control || it.key]
            const then = it.effective
            return typeof then === "string"
                ? now !== then
                : !(Math.abs(now - then) <= 1e-9 * Math.max(1, Math.abs(then)))
        })
    }
    const onChange = async () => {
        settings = track.getSettings()
        // console.log('configurationchange event: current settings:', settings);
        if (busy || track.readyState !== "live" || !drifted()) return
        busy = true
        try {
            const again = await lockCamera(track, report.resolvedProfile, {
                ...options,
                keepLocked: false,
            })
            if (options.onRelock) options.onRelock(again)
        } finally {
            busy = false
        }
    }
    track.addEventListener("configurationchange", onChange)
    return () => track.removeEventListener("configurationchange", onChange)
}

/** Put white balance, exposure and focus back to continuous auto where offered. */
async function unlockCamera(track) {
    const caps =
        typeof track.getCapabilities === "function"
            ? track.getCapabilities()
            : {}
    const errors = []
    for (const m of MODE_KEYS) {
        if (!Array.isArray(caps[m]) || !caps[m].includes("continuous")) continue
        const err = await tryApply(track, { [m]: "continuous" })
        if (err) errors.push(`${m}: ${err}`)
    }
    return errors
}

/**
 * Turn the camera's current values into a fully manual profile you can store and
 * pass to lockCamera() later. Only controls this browser/camera exposes are included.
 */
function profileFromSettings(track, platform = detectPlatform()) {
    const caps =
        typeof track.getCapabilities === "function"
            ? track.getCapabilities()
            : {}
    const s = track.getSettings()
    // console.log('Camera current settings:', s);
    const p = {}
    for (const [modeKey, valueKey] of GROUPS) {
        if (Array.isArray(caps[modeKey]) && caps[modeKey].includes("manual"))
            p[modeKey] = "manual"
        if (isRange(caps[valueKey]) && Number.isFinite(s[valueKey]))
            p[valueKey] = s[valueKey]
    }
    for (const key of SINGLE_KEYS) {
        if (!isRange(caps[key]) || !Number.isFinite(s[key])) continue
        if (key === "exposureCompensation") {
            // Windows: this is the UVC gain. Elsewhere it is an auto-exposure bias with
            // no effect once exposure is manual, so it is left out.
            if (platform === "Windows") p.gain = s[key]
            continue
        }
        p[key] = s[key]
    }
    return p
}

function fmt(v) {
    return v === undefined
        ? "—"
        : typeof v === "number"
          ? String(Number(v.toPrecision(8)))
          : String(v)
}

/** Plain-text table of a lockCamera() report, for logs. */
function formatReport(report) {
    const fmt = (v) =>
        v === undefined
            ? "—"
            : typeof v === "number"
              ? String(Number(v.toPrecision(8)))
              : String(v)
    const rows = [
        ["control", "requested", "sent", "effective", "status", "note"],
    ]
    for (const it of report.items)
        rows.push([
            it.key,
            fmt(it.requested),
            fmt(it.sent),
            fmt(it.effective),
            it.status,
            it.note || "",
        ])
    const widths = rows[0].map((_, i) =>
        Math.max(...rows.map((r) => r[i].length)),
    )
    const lines = rows.map((r) =>
        r
            .map((c, i) => (i === r.length - 1 ? c : c.padEnd(widths[i])))
            .join("  ")
            .trimEnd(),
    )
    return `${report.label || "camera"} on ${report.platform}: ${report.ok ? "locked" : "NOT fully locked"}\n${lines.join("\n")}`
}

// document.getElementById("fromCamera").addEventListener("click", async () => {
//     console.log("")
//     console.log("\nfromCamera clicked")
//     const SETTINGS = getCurrentCameraSetting(
//         document.querySelector("video").srcObject.getVideoTracks()[0],
//     )
//     console.log("Current camera settings:", SETTINGS)
//     // const MIN_SETTINGS = getMinimumCameraSetting(document.querySelector('video').srcObject.getVideoTracks()[0]);
//     // console.log("Minimum camera settings:", MIN_SETTINGS);
//     // const MAX_SETTINGS = getMaximumCameraSetting(document.querySelector('video').srcObject.getVideoTracks()[0]);
//     // console.log("Maximum camera settings:", MAX_SETTINGS);
//     // const POSSIBLE_RESOLUTIONS = getCameraPossibleResolutions(document.querySelector('video').srcObject.getVideoTracks()[0]);
//     // console.log("Possible camera resolutions:", POSSIBLE_RESOLUTIONS);
// })

// --------------

function getCurrentCameraSetting(track) {
    // this function extracts all values
    let capabilities = track.getCapabilities()
    let settings = track.getSettings()
    const currentSettings = {}
    for (const key of CONTROL_KEYS) {
        if (key in capabilities && key in settings) {
            currentSettings[key] = settings[key]
        }
    }
    return currentSettings
}

function getMinimumCameraSetting(track) {
    let capabilities = track.getCapabilities()
    const minSettings = {}
    for (const key of CONTROL_KEYS) {
        if (key in capabilities && isRange(capabilities[key])) {
            minSettings[key] = capabilities[key].min
        }
    }
    return minSettings
}

function getMaximumCameraSetting(track) {
    let capabilities = track.getCapabilities()
    const maxSettings = {}
    for (const key of CONTROL_KEYS) {
        if (key in capabilities && isRange(capabilities[key])) {
            maxSettings[key] = capabilities[key].max
        }
    }
    return maxSettings
}

function getCameraPossibleResolutions(track) {
    let capabilities = track.getCapabilities()
    const possibleResolutions = {}
    if ("width" in capabilities && "height" in capabilities) {
        possibleResolutions["width"] = capabilities["width"]
        possibleResolutions["height"] = capabilities["height"]
    }
    return possibleResolutions
}

function applyCameraSettings(track, settings) {
    const constraints = {}
    for (const key of CONTROL_KEYS) {
        if (key in settings) {
            constraints[key] = settings[key]
        }
    }
    track
        .applyConstraints(constraints)
        .then(() => {
            console.log("Camera settings applied successfully.")
        })
        .catch((error) => {
            console.error("Error applying camera settings:", error)
        })
}

function useManualSettings(track) {
    const autoSettings = {
        whiteBalanceMode: "manual",
        exposureMode: "manual",
        focusMode: "manual",
    }
    applyCameraSettings(track, autoSettings)
}

function useAutoSettings(track) {
    const autoSettings = {
        whiteBalanceMode: "continuous",
        exposureMode: "continuous",
        focusMode: "continuous",
    }
    applyCameraSettings(track, autoSettings)
}
