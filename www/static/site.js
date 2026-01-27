function data_href() {
    document.querySelectorAll("[data-href]").forEach(function(element) {
        element.addEventListener("click", function(event) {
            window.location.href = element.dataset.href;
        });
    });
}

document.addEventListener("DOMContentLoaded", function(event) {
    data_href();
});
