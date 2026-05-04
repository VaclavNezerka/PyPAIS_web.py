document.addEventListener("DOMContentLoaded", async () => {
    const currentLang = document.body.dataset.currentLang
    const preferredLang = localStorage.getItem("preferredLang")

    console.log("Report :")
    console.log("Current language:", currentLang)
    console.log("Preferred language:", preferredLang)
    console.log("Preferred language:", preferredLang)
    if (preferredLang && preferredLang !== currentLang) {
        await fetch(`/switch-language/${preferredLang}`, { method: "POST" })
        console.log("Language switched to:", preferredLang)
        document.body.dataset.currentLang = preferredLang
        location.reload()
    }

    document.getElementById("current-lang-icon").src =
        "/static/language_icons/icon_" + currentLang + ".png"

    document.querySelectorAll(".lang-menu a").forEach((link) => {
        link.addEventListener("click", async (e) => {
            // e.preventDefault();
            const langBtn = document.getElementById("current-lang-btn")
            const selectedLang = link.id
            langBtn.value = selectedLang
            if (selectedLang !== currentLang) {
                switchLanguage(selectedLang).then(() => {
                    location.reload()
                })
            }
        })
    })
})

// // Save the choice locally
async function switchLanguage(lang) {
    document.getElementById("current-lang-icon").src =
        "/static/language_icons/icon_" + lang + ".png"
    await fetch("/switch-language/" + lang, { method: "POST" })
    localStorage.setItem("preferredLang", lang)
}
