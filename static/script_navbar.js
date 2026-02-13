const menu = document.getElementById("menu")
// const hamburger = document.getElementById("menu")

hamburger.addEventListener("click", () => {
    menu.classList.toggle("active")
    antimenu.classList.toggle("active")
})

// document.getElementById("hamburger").addEventListener("click", () => {
//     console.log("clicked")
//     const isHidden = window.getComputedStyle(menu).display === "none"

//     menu.style.display = isHidden ? "block" : "none"
// })
