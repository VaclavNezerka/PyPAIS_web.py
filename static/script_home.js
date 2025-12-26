document.getElementById("TryDemoBtn").addEventListener("click", function () {
    console.log("Try Demo button clicked")
    document.getElementById("demo_section").scrollIntoView({
        behavior: "smooth",
        // block: "start",
        // inline: "nearest",
    })
})
