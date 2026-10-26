// language switcher (navbar) - the choice is kept in the session and in localStorage
async function switchLanguage(lang) {
    await fetch("/switch-language/" + lang, { method: "POST" })
    try {
        localStorage.setItem("preferredLang", lang)
    } catch (e) {}
}

document.addEventListener("DOMContentLoaded", async () => {
    const currentLang = document.body.dataset.currentLang
    let preferredLang = null
    try {
        preferredLang = localStorage.getItem("preferredLang")
    } catch (e) {}

    // a new session starts in the browser's language - restore the user's choice
    // (at most once per 10 s, so a failing switch can't cause a reload loop)
    const lastRestore = Number(sessionStorage.getItem("langRestoreAt") || 0)
    if (preferredLang && preferredLang !== currentLang && Date.now() - lastRestore > 10000) {
        sessionStorage.setItem("langRestoreAt", String(Date.now()))
        await switchLanguage(preferredLang)
        location.reload()
        return
    }

    document.querySelectorAll("#langMenu [data-lang]").forEach((button) => {
        button.addEventListener("click", async () => {
            const lang = button.dataset.lang
            if (lang !== currentLang) {
                await switchLanguage(lang)
                location.reload()
            }
        })
    })
})
