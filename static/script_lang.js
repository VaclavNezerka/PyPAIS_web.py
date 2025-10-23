// Save the choice locally
async function switchLanguage(lang) {
    document.getElementById('current-lang-icon').src = '/static/language_icons/icon_' + lang + '.png';
    await fetch('/switch-language/' + lang, { method: 'POST' });
    localStorage.setItem('preferredLang', lang);
}
                
document.addEventListener("DOMContentLoaded", () => {
    const currentIcon = document.getElementById("current-lang-icon");
    currentIcon.src = '/static/language_icons/icon_' + localStorage.getItem('preferredLang') + '.png';

    document.querySelectorAll(".lang-menu a").forEach(link => {
        link.addEventListener("click", async (e) => {
            // e.preventDefault();
            const langBtn = document.getElementById("current-lang-btn");
            const selectedLang = link.id;
            // const selectedIcon = '/static/language_icons/icon_' + selectedLang + '.png';
            const currentLang = langBtn.value;
            langBtn.value = selectedLang;
            await switchLanguage(selectedLang);
            location.reload();
        });
    });
});


