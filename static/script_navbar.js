// mobile navigation toggle
const navToggle = document.getElementById("navToggle")
const appNav = document.getElementById("appNav")

navToggle?.addEventListener("click", () => {
    const open = appNav.classList.toggle("is-open")
    navToggle.setAttribute("aria-expanded", String(open))
})
