/* Global HTMX + Lucide + Alpine initialization helpers */
document.addEventListener("DOMContentLoaded", () => {
    if (window.lucide) {
        window.lucide.createIcons();
    }
});

document.body.addEventListener("htmx:afterSwap", () => {
    if (window.lucide) {
        window.lucide.createIcons();
    }
});
