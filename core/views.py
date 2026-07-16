"""
Views for the core (public website) app — Campora's public-facing pages.

Campora is a multi-college platform: students browse Colleges first, then
that college's Courses. `core` owns all public pages; `courses` owns the
College/Course models; `admissions` owns Enquiry. See SYSTEM_ARCHITECTURE.docx.
"""
import logging

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from courses.models import College, Course

from .forms import ContactForm

logger = logging.getLogger(__name__)

# Number of colleges featured on the Home page.
FEATURED_COLLEGE_COUNT = 3


def home(request):
    """Public home page: hero, platform stats, featured colleges, CTA.

    Only APPROVED colleges are ever shown publicly — pending/rejected/
    suspended colleges are an internal, Super-Admin-only concern (the
    approval workflow UI itself is a future phase; the data model is
    ready for it now via College.status).
    """
    approved_colleges = College.objects.filter(status=College.Status.APPROVED)
    featured_colleges = approved_colleges.annotate(
        course_count=Count("courses", filter=Q(courses__is_active=True))
    )[:FEATURED_COLLEGE_COUNT]

    stats = {
        "college_count": approved_colleges.count(),
        "course_count": Course.objects.filter(is_active=True, college__status=College.Status.APPROVED).count(),
    }
    context = {"featured_colleges": featured_colleges, "stats": stats}
    return render(request, "core/home.html", context)


def about(request):
    """About page: the Campora platform, its mission, vision and values."""
    return render(request, "core/about.html")


def colleges(request):
    """Public colleges directory — search by name/city/state, filter by state.

    Only APPROVED colleges are listed. Search/filter are simple GET-param
    based (no JS/AJAX) to keep this phase's scope focused on the data model
    and browsing flow rather than a heavier search UI.
    """
    college_qs = College.objects.filter(status=College.Status.APPROVED).annotate(
        course_count=Count("courses", filter=Q(courses__is_active=True))
    )

    query = request.GET.get("q", "").strip()
    if query:
        college_qs = college_qs.filter(
            Q(name__icontains=query) | Q(city__icontains=query) | Q(state__icontains=query)
        )

    state = request.GET.get("state", "").strip()
    if state:
        college_qs = college_qs.filter(state=state)

    available_states = (
        College.objects.filter(status=College.Status.APPROVED)
        .exclude(state="")
        .values_list("state", flat=True)
        .distinct()
        .order_by("state")
    )

    context = {
        "colleges": college_qs,
        "query": query,
        "selected_state": state,
        "available_states": available_states,
    }
    return render(request, "core/colleges.html", context)


def college_detail(request, slug):
    """A single college's public profile: description, contact info, and
    its currently active courses."""
    college = get_object_or_404(College, slug=slug, status=College.Status.APPROVED)
    active_courses = college.courses.filter(is_active=True)
    context = {"college": college, "courses": active_courses}
    return render(request, "core/college_detail.html", context)


def courses(request):
    """Public courses listing, grouped by college.

    Only shows active courses belonging to approved colleges. Ordering
    matches Course.Meta.ordering (college__name, course_name), which is a
    requirement for Django's {% regroup %} template tag to group correctly.
    """
    active_courses = Course.objects.filter(
        is_active=True, college__status=College.Status.APPROVED
    ).select_related("college")
    context = {"courses": active_courses}
    return render(request, "core/courses.html", context)


def contact(request):
    """Platform-level contact page. Individual colleges' own contact
    details live on their respective College Detail pages.

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
