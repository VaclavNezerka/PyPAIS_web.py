if ("serviceWorker" in navigator) {
    // unregister the service worker worker_0.js
    navigator.serviceWorker.getRegistrations().then(function (registrations) {
        for (let registration of registrations) {
            registration.unregister()
        }
    })
}
// // register the service worker worker_0.js
// if ("serviceWorker" in navigator) {
//     navigator.serviceWorker
//         .register("/static/worker_0.js", { scope: "/static/" })
//         .then((registration) => {
//             console.log(
//                 "Service Worker registered with scope:",
//                 registration.scope,
//             )
//         })
//         .catch((error) => {
//             console.error("Service Worker registration failed:", error)
//         })
// }
// import save from script.js
// import {activateExperiment} from './script.js';

async function fetchAlerts() {
    const alerts = await fetch("/translations-alerts", { method: "GET" }).then(
        (response) => response.json(),
    )
    return alerts
}

async function main() {
    const alerts = await fetchAlerts()
    // console.log(alerts)
}

main()
let alerts = {}
fetchAlerts().then((data) => {
    alerts = data
})
// console.log(alerts)

function editExperimentId(id) {
    // Get the experiment id
    const uniqueQuery = "?nocache=" + new Date().getTime()
    fetch("/activate-experiment/" + id + uniqueQuery, { method: "POST" })
        .then((response) => response.json())
        .then((data) => {
            if (data.status === "success") {
                window.location.href = "/"
            }
        })
        .catch((error) => {
            console.error("Error:", error)
        })
}

async function exportExperimentPDF(ids) {
    // window.location.href = "/export-report/"
    console.log("Exporting experiments with IDs:", ids)
    // document.getElementById("experiment_ids").value = ids.join(",")
    // console.log(document.getElementById("experiment_ids").value)

    const response = await fetch("/export-report/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            Accept: "application/pdf",
        },
        // body: JSON.stringify({
        //     experiment_ids: ids,
        // }),
    })

    if (!response.ok) {
        throw new Error("Export failed")
    }

    // const blob = await response.blob()
    // const url = window.URL.createObjectURL(blob)

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)

    const a = document.createElement("a")
    a.href = url
    a.download = "experiments.pdf"
    document.body.appendChild(a)
    a.click()
    window.open(url, "_blank")
    a.remove()
    window.URL.revokeObjectURL(url)
}

// async function exportExperimentPDF(ids) {
//     // Get the experiment ids
//     // redirect to the experiment page
//     window.location.href = "/export-report/"

//     const uniqueQuery = "?nocache=" + new Date().getTime()
//     fetch("/export-report/", {
//         method: "POST",
//         headers: {
//             "Content-Type": "application/json",
//         },
//         body: JSON.stringify({ experiment_ids: ids }),
//     })
//         .then((response) => response.json())
//         .then((data) => {
//             if (data.status === "success") {
//                 // download the pdf file
//                 const link = document.createElement("a")
//                 link.href = data.file_url + uniqueQuery
//                 link.download = "experiments.pdf"
//                 document.body.appendChild(link)
//                 link.click()
//                 document.body.removeChild(link)
//             }
//         })
//         .catch((error) => {
//             console.error("Error:", error)
//         })
// }

async function deleteExperimentId(id, skipConfirm = false) {
    if (skipConfirm === false) {
        if (
            !confirm(
                alerts.confirmDeleteExperiment +
                    id +
                    "?\n" +
                    alerts.actionCannotBeUndone,
            )
        ) {
            return
        }
    }

    // Get the experiment id
    const uniqueQuery = "?nocache=" + new Date().getTime()
    fetch("/delete-experiment/" + id + uniqueQuery, { method: "POST" })
        .then((response) => response.json())
        .then((data) => {
            if (data.status === "success") {
                window.location.reload()
            }
        })
        .catch((error) => {
            console.error("Error:", error)
        })
}

function callQueryStringURL(queryString) {
    // Get the query string
    window.location.search = queryString
}

function excludeFromSearchQuery(queryKey) {
    const currentQueryString = window.location.search
    const keys = currentQueryString.split("&").map((key) => key.split("=")[0])
    if (keys.includes(queryKey)) {
        const newQueryString = currentQueryString.replace(
            queryKey +
                "=" +
                currentQueryString.split(queryKey + "=")[1].split("&")[0],
            "",
        )
        callQueryStringURL(newQueryString)
    }
}

function concatenateSearchQuery(queryString) {
    const key = queryString.split("=")[0] + "="
    const value = queryString.split("=")[1].split("&")[0]
    const currentQueryString = window.location.search

    // current query keys
    let noQuestionMark = currentQueryString.split("?")[1]
    if (noQuestionMark == undefined) {
        noQuestionMark = currentQueryString
    }
    const keys = noQuestionMark.split("&").map((key) => key.split("=")[0] + "=")
    // if any key == queryString key, replace the value
    let newQueryString = ""
    if (keys.includes(key)) {
        id = keys.indexOf(key)
        const currentValue = currentQueryString.split(keys[id])[1].split("&")[0]
        newQueryString = currentQueryString.replace(
            keys[id] + currentValue,
            key + value,
        )
    } else {
        newQueryString = currentQueryString + "&" + queryString
    }
    callQueryStringURL(newQueryString)
}

document.getElementById("previous_page").addEventListener("click", function () {
    current_page = parseInt(document.getElementById("current_page").innerText)
    if (current_page == 1) {
        current_page = 1
    } else {
        current_page -= 1
    }
    document.getElementById("current_page").innerText = current_page
    concatenateSearchQuery("page=" + current_page)
})
document.getElementById("next_page").addEventListener("click", function () {
    current_page = parseInt(document.getElementById("current_page").innerText)
    current_page += 1
    document.getElementById("current_page").innerText = current_page
    concatenateSearchQuery("page=" + current_page)
})

document.getElementById("sortBy").addEventListener("change", function () {
    const sortBy = this.value
    instructions = sortBy.replace(/\s+/g, "").split(",")
    sort_order = ""
    for (let i = 0; i < instructions.length; i++) {
        switch (instructions[i].toLowerCase()) {
            case "id":
                sort_order += "id,"
                break
            case "asphaltratio":
                sort_order += "asphalt_ratio,"
                break
            case "expertguess":
                sort_order += "expert_guess,"
                break
            case "date":
                sort_order += "time_stamp,"
                break
            case "state":
                sort_order += "current_state,"
                break
            default:
                break
        }
    }
    sort_order = sort_order.slice(0, -1)
    if (sort_order == "") {
        excludeFromSearchQuery("sort_by")
    } else {
        concatenateSearchQuery("sort_by=" + sort_order)
    }
})

document.getElementById("maxRecords").addEventListener("change", function () {
    const maxRecords = this.value
    concatenateSearchQuery("page_limit=" + maxRecords)
})

document.getElementById("sortOrder").addEventListener("change", function () {
    const sortOrder = this.value
    concatenateSearchQuery("sort_order=" + sortOrder)
})

document.addEventListener("DOMContentLoaded", function () {
    // Restore any other field states as necessary (e.g., input values, checkboxes)

    // Get query parameters from the URL
    const urlParams = new URLSearchParams(window.location.search)

    // Restore page number
    const page = urlParams.get("page")
    if (page) {
        document.getElementById("current_page").innerText = page
    }
    // Restore sort order
    const sortBy = urlParams.get("sort_by")
    if (sortBy) {
        dictionary = {
            id: "id",
            asphalt_ratio: "Asphalt Ratio",
            expert_guess: "Expert Guess",
            time_stamp: "Date",
            current_state: "State",
        }
        document.getElementById("sortBy").value = sortBy
            .split(",")
            .map((key) => dictionary[key])
            .join(", ")
    }
    const maxRecords = Number(urlParams.get("page_limit"))
    if (maxRecords) {
        document.getElementById("maxRecords").value = maxRecords
    }
    const sortOrder = urlParams.get("sort_order")
    if (sortOrder) {
        document.getElementById("sortOrder").value = sortOrder
    }
})

// document.getElementById('fileInput').addEventListener('change', function() {

// });

// function uploadFiles(filesUploaded) {
//     let files = Array.from(filesUploaded);
//     return new Promise(async (resolve, reject) => {
//         try {
//             for (let i = 0; i < files.length; i++) {
//                 console.log('Uploading file...', i);
//                 const formData = new FormData();
//                 formData.append('file', files[i]);
//             await fetch('/backup-storage', { method: 'POST' });
//             await Promise.all([
//                 fetch('/remove-background', { method: 'POST', body: formData }),
//                 fetch('/grayscale-data', { method: 'POST', body: formData }),
//             ])
//             await fetch('/entropy', { method: 'POST', body: formData })
//             await fetch('/apply-mask', { method: 'POST' });
//             await fetch('/save?status=processing', { method: 'POST' }).catch((error) => {
//                 console.error('Error:', error);
//             });
//             await fetch('restore-storage', { method: 'POST' });
//         }
//         // window.location.reload();
//         resolve();
//     }
//      catch (error) {
//         reject(error);
//     }
//     });
// }

let progress = document.getElementById("fileProgress")
let totalFiles = 0
let uploadedFiles = 0

document.querySelectorAll("fileInput").forEach((element) => {
    element.addEventListener("change", () => {
        const filesUploaded = element.files
        progress.style.display = "block"
        document.getElementById("fileProgressDiv").style.display = "block"
        totalFiles = filesUploaded.length

        // pass the files to the service worker
        const worker = new Worker("/static/worker_0.js")
        worker.postMessage({ filesUploaded })
        worker.onmessage = function (e) {
            if (e.data === "success") {
                console.log("Success:", e.data)
                window.location.reload()
            } else if (e.data === "report") {
                uploadedFiles++
                console.log(
                    "Uploading file...",
                    (uploadedFiles / totalFiles) * 100,
                )
                progress.value = (uploadedFiles / totalFiles) * 100
                if (uploadedFiles === totalFiles) {
                    progress.style.display = "none"
                    uploadedFiles = 0
                    totalFiles = 0
                } else {
                    console.log("Uploading file...", uploadedFiles)
                }
                console.log("Success:", e.data)
            } else {
                console.error("Error:", e.data)
            }
        }
    })
})

window.addEventListener("message", function (e) {
    if (e.data === "success") {
        window.location.reload()
    } else if (e.data === "report") {
        progress.value = (e.data / totalFiles) * 100
        if (uploadedFiles === totalFiles) {
            progress.style.display = "none"
        } else {
            console.log("Uploading file...", uploadedFiles)
        }
        console.log("Success:", e.data)
    } else {
        console.error("Error:", e.data)
    }
})

function changeAdminPrivileges(username, willBeAdmin) {
    uniqueQuery = "?nocache=" + new Date().getTime()
    form = new FormData()
    form.append("username", username)
    form.append("will_be_admin", willBeAdmin)

    fetch("/change-admin-privileges", {
        method: "POST",
        body: form,
    })
        .then((response) => response.json())
        .then((data) => {
            if (data.status === "success") {
                window.location.reload()
            }
        })
        .catch((error) => {
            console.error("Error:", error)
            // window.location.reload()
        })
}

function changeUserBlockade(username, willBeBlocked) {
    uniqueQuery = "?nocache=" + new Date().getTime()
    form = new FormData()
    form.append("username", username)
    form.append("will_be_blocked", willBeBlocked)
    fetch("/change-user-blockade", {
        method: "POST",
        body: form,
    })
        .then((response) => response.json())
        .then((data) => {
            if (data.status === "success") {
                window.location.reload()
            }
        })
        .catch((error) => {
            console.error("Error:", error)
            window.location.reload()
        })
}

let checkboxes = []

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("#record-checkbox").forEach((checkbox) => {
        checkbox.addEventListener("change", () => {
            const id = checkbox.getAttribute("data-id")
            if (checkbox.checked) {
                checkboxes.push(id)
            } else {
                checkboxes = checkboxes.filter((item) => item !== id)
            }
            // console.log(checkboxes)
        })
    })
})

function initButtons() {
    // Delete button listener
    document.querySelectorAll(".btn-cancel").forEach((button) => {
        button.addEventListener("click", () => {
            if (checkboxes.length === 0) {
                alert(alerts.noExperimentsSelectedforDeletion)
                return
            }
            if (
                !confirm(
                    alerts.sureDeleteExperiments +
                        "\n" +
                        checkboxes +
                        "\n" +
                        alerts.cannotBeUndone,
                )
            ) {
                return
            }
            for (let id of checkboxes) {
                deleteExperimentId(id, true)
            }
        })
    })

    // Edit button listener
    document.querySelectorAll(".btn-details").forEach((button) => {
        button.addEventListener("click", () => {
            if (checkboxes.length === 0) {
                alert(alerts.selectExperimetnsToViewDetails)
                return
            }
            if (checkboxes.length > 1) {
                alert(alerts.selectJustOneExperimetnsToViewDetails)
                return
            }
            editExperimentId(checkboxes[0], true)
        })
    })

    // Export button listener
    document.querySelectorAll(".btn-export").forEach((button) => {
        button.addEventListener("click", () => {
            if (checkboxes.length === 0) {
                alert(alerts.selectAtLeastOneExperimentForExport)
                return
            }
            if (checkboxes.length == 1) {
                if (
                    !confirm(
                        alerts.exportSingleExperimentNotAllowed +
                            "\n" +
                            alerts.exportSingleExperimentProceeding,
                    )
                ) {
                    return
                }
            }
            window.location.href = "/export-report/" + checkboxes.join(",")
        })
    })

    document
        .querySelectorAll("#btn-grant-admin-privileges")
        .forEach((button) => {
            button.addEventListener("click", () => {
                if (confirm(alerts.grantAdmin + "\n" + checkboxes)) {
                    if (checkboxes.length === 0) {
                        alert(alerts.noEmployeesSelected)
                        return
                    }
                    for (let username of checkboxes) {
                        changeAdminPrivileges(username, true)
                    }
                }
            })
        })

    document
        .querySelectorAll("#btn-remove-admin-privileges")
        .forEach((button) => {
            button.addEventListener("click", () => {
                if (confirm(alerts.removeAdmin + "\n" + checkboxes)) {
                    if (checkboxes.length === 0) {
                        alert(alerts.noEmployeesSelected)
                        return
                    }
                    for (let username of checkboxes) {
                        changeAdminPrivileges(username, false)
                    }
                }
            })
        })

    document.querySelectorAll("#btn-block-user").forEach((button) => {
        button.addEventListener("click", () => {
            if (confirm(alerts.blockUser + "\n" + checkboxes)) {
                if (checkboxes.length === 0) {
                    alert(alerts.noEmployeesSelected)
                    return
                }
                for (let username of checkboxes) {
                    changeUserBlockade(username, true)
                }
            }
        })
    })

    document.querySelectorAll("#btn-unblock-user").forEach((button) => {
        button.addEventListener("click", () => {
            if (confirm(alerts.unblockUser + "\n" + checkboxes)) {
                if (checkboxes.length === 0) {
                    alert(alerts.noEmployeesSelected)
                    return
                }
                for (let username of checkboxes) {
                    changeUserBlockade(username, false)
                }
            }
        })
    })
}

initButtons()

// OLD LISTENERS - USED FOR EACH BUTTON IN THE TABLE ROW
// document.addEventListener("DOMContentLoaded", () => {
//     document.querySelectorAll(".btn-details").forEach((button) => {
//         button.addEventListener("click", () => {
//             const id = button.getAttribute("data-id")
//             editExperimentId(id)
//             //   console.log('Continue experiment with ID:', id);
//         })
//     })
// })

// document.addEventListener("DOMContentLoaded", () => {
//     document.querySelectorAll(".btn-cancel").forEach((button) => {
//         button.addEventListener("click", () => {
//             const id = button.getAttribute("data-id")
//             deleteExperimentId(id)
//             //   console.log('Delete experiment with ID:', id);
//         })
//     })
// })

// document.addEventListener("DOMContentLoaded", () => {
//     document.querySelectorAll(".btn-export").forEach((button) => {
//         button.addEventListener("click", () => {
//             const id = button.getAttribute("data-id")
//             exportExperimentPDF(id)
//             //   console.log('Delete experiment with ID:', id);
//         })
//     })
// })
