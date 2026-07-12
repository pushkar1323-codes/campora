"""
Views for the core (public website) app — Campora's public-facing pages.

Per SYSTEM_ARCHITECTURE.docx, the `core` app owns the public website; the
`Course` model itself is owned and managed by the `courses` app (staff CRUD
for courses arrives in Phase 12). These views only read course data.
"""
import logging

from django.contrib import messages
from django.shortcuts import redirect, render

from courses.models import Course

from .forms import ContactForm

logger = logging.getLogger(__name__)

# Number of active courses to feature on the Home page preview section.
FEATURED_COURSE_COUNT = 3


def home(request):
    """Public home page: hero, about preview, featured courses, CTA."""
    featured_courses = Course.objects.filter(is_active=True)[:FEATURED_COURSE_COUNT]
    context = {"featured_courses": featured_courses}
    return render(request, "core/home.html", context)


def about(request):
    """About page: institute information, vision and mission."""
    return render(request, "core/about.html")


def courses(request):
    """Public courses listing — only shows currently active courses."""
    active_courses = Course.objects.filter(is_active=True)
    context = {"courses": active_courses}
    return render(request, "core/courses.html", context)


def contact(request):
    """Contact page: institute contact details + a general enquiry form.

    Uses the Post/Redirect/Get pattern so refreshing the confirmation page
    never resubmits the form. The message is not persisted to the database
    (see core/forms.py docstring) — it is validated and acknowledged; wiring
    it to email/storage can be added in a later phase if required.
    """
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            logger.info(
                "Contact form submitted by %s <%s>: %s",
                form.cleaned_data["full_name"],
                form.cleaned_data["email"],
                form.cleaned_data["subject"],
            )
            messages.success(
                request,
                "Thank you for reaching out! Our team will get back to you shortly.",
            )
            return redirect("core:contact")
    else:
        form = ContactForm()

    return render(request, "core/contact.html", {"form": form})
