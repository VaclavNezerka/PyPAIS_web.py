document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".flash-message").forEach((el) => {
        const msg = el.dataset.message
        if (msg) alert(msg)
    })
})

function onSubmit(token) {
    document.getElementById("form-recaptcha-protected").submit()
}
