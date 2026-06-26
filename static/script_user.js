// User endpoints
document.querySelectorAll("#changePasswordButton").forEach(function (button) {
    button.addEventListener("click", function () {
        // redirect to change password page
        window.location.href = "/change-password"
    })
})

document.querySelectorAll("#changeEmailButton").forEach(function (button) {
    button.addEventListener("click", function () {
        // redirect to change email page
        window.location.href = "/change-email"
    })
})

document
    .querySelectorAll("#editPersonalInformationButton")
    .forEach(function (button) {
        button.addEventListener("click", function () {
            // redirect to edit personal info page
            window.location.href = "/edit-personal-information"
        })
    })

// COMPANY -- endpoints
document
    .querySelectorAll("#changeCompanyEmailButton")
    .forEach(function (button) {
        button.addEventListener("click", function () {
            // redirect to change company email page
            window.location.href = "/change-company-email"
        })
    })

document
    .querySelectorAll("#editCompanyInformationButton")
    .forEach(function (button) {
        button.addEventListener("click", function () {
            // redirect to edit company info page
            window.location.href = "/edit-company-information"
        })
    })

// COMPANY key management
document
    .querySelectorAll("#regenerateCompanyKeyButton")
    .forEach(function (button) {
        button.addEventListener("click", function () {
            // redirect to regenerate company key page
            window.location.href = "/regenerate-company-key"
        })
    })

document.querySelectorAll("#viewCompanyKeyButton").forEach(function (button) {
    button.addEventListener("click", function () {
        // redirect to regenerate company key page
        window.location.href = "/view-company-key"
    })
})

document.addEventListener("DOMContentLoaded", function () {
    // if page is view-company-key, show alert about security
    if (window.location.pathname === "/view-company-key") {
        // wait 500ms and then show alert
        setTimeout(function () {
            // redirect to company after 10 seconds
            window.location.href = "/company"
        }, 10000)
    }
})

document.addEventListener("DOMContentLoaded", function () {
    // if page is view-company-key, show alert about security
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
                    }
                }
            }
        })
})

document.querySelectorAll(".modern-input").forEach(function (input) {
    // input.addEventListener("change", function () {
    input.addEventListener("input", function () {
        fetch("/update-default-experiment-info", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                field: input.id,
                value: input.value,
            }),
        })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Network response was not ok")
                }
                return response.json()
            })
            .catch((error) => {
                console.error("Error updating default experiment info:", error)
            })
    })
})
