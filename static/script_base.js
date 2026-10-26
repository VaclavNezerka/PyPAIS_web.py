// reCAPTCHA v3 callback of the protected forms (form_plain.html) - flash messages are handled by ui.js
function onSubmit(token) {
    document.getElementById("form-recaptcha-protected").submit()
}
