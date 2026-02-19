// // Save the choice locally
// async function switchLanguage(lang) {
//     document.getElementById("current-lang-icon").src =
//         "/static/language_icons/icon_" + lang + ".png"
//     await fetch("/switch-language/" + lang, { method: "POST" })
//     localStorage.setItem("preferredLang", lang)
// }

// document.addEventListener("DOMContentLoaded", () => {
//     const currentIcon = document.getElementById("current-lang-icon")
//     const currentLang = document.body.dataset.currentLang
//     if (localStorage.getItem("preferredLang")) {
//         switchLanguage(localStorage.getItem("preferredLang", currentLang))
//     }

//     document.querySelectorAll(".lang-menu a").forEach((link) => {
//         link.addEventListener("click", async (e) => {
//             // e.preventDefault();
//             const langBtn = document.getElementById("current-lang-btn")
//             const selectedLang = link.id
//             // const selectedIcon = '/static/language_icons/icon_' + selectedLang + '.png';
//             const currentLang = langBtn.value
//             langBtn.value = selectedLang
//             switchLanguage(selectedLang).then(() => {
//                 location.reload()
//             })
//         })
//     })

//     currentIcon.src =
//         "/static/language_icons/icon_" +
//         localStorage.getItem("preferredLang") +
//         ".png"
// })

// Save the choice locally
async function switchLanguage(lang) {
    document.getElementById("current-lang-icon").src =
        "/static/language_icons/icon_" + lang + ".png"
    await fetch("/switch-language/" + lang, { method: "POST" })
    localStorage.setItem("preferredLang", lang)
}

document.addEventListener("DOMContentLoaded", () => {
    const currentIcon = document.getElementById("current-lang-icon")
    const currentLang = document.body.dataset.currentLang
    selected_lang = localStorage.getItem("preferredLang") || currentLang
    console.log("Current language:", selected_lang)
    if (selected_lang) {
        if (selected_lang !== currentLang) {
            switchLanguage(selected_lang).then(() => {
                location.reload()
            })
        }
    }
    // if (currentLang) {
    //     switchLanguage(currentLang).then(() => {
    //         location.reload()
    //     })
    // }
    // if (localStorage.getItem("preferredLang")) {
    //     switchLanguage(localStorage.getItem("preferredLang", currentLang))
    // }

    currentIcon.src =
        "/static/language_icons/icon_" +
        // localStorage.getItem("preferredLang") +
        document.body.dataset.currentLang +
        ".png"

    document.querySelectorAll(".lang-menu a").forEach((link) => {
        link.addEventListener("click", async (e) => {
            // e.preventDefault();
            const langBtn = document.getElementById("current-lang-btn")
            const selectedLang = link.id
            // const selectedIcon = '/static/language_icons/icon_' + selectedLang + '.png';
            const currentLang = langBtn.value
            langBtn.value = selectedLang
            switchLanguage(selectedLang).then(() => {
                location.reload()
            })
        })
    })
})
