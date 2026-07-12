// College Admission Enquiry Management System — global JS entry point.
// Feature-specific scripts (toast notifications, dark mode, form validation)
// are added in their respective phases per IMPLEMENTATION_PLAN.docx.

document.addEventListener('DOMContentLoaded', function () {
    // Enable Bootstrap tooltips globally, if any are present on a page.
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggerList.forEach(function (el) {
        new bootstrap.Tooltip(el);
    });
});
