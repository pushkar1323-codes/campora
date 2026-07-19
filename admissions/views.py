"""
Views for the admissions app — Phase 4: Admission Enquiry.

Students always arrive here from a specific Course's "Enquire Now" button
(a college's Course card — see templates/partials/course_card.html), so the
course — and therefore its college — is already fixed by the URL. There is
no standalone "submit an enquiry" entry point that asks for College/Course
via a dropdown, per SYSTEM_ARCHITECTURE.docx section 14 ("Students never
browse standalone courses... They always: Browse College -> View Courses of
that College -> Submit Enquiry").

Per SYSTEM_ARCHITECTURE.docx section 6, students submit enquiries without
authentication in Version 1.0 — anonymous submission is allowed. If a
Student happens to be logged in, the enquiry is automatically linked to
their account via `submitted_by` (Enquiry.submitted_by is nullable so this
never blocks anonymous visitors).
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from courses.models import College, Course

from .forms import EnquiryForm, EnquirySelfEditForm
from .models import Enquiry
from .services import (
    can_student_edit_enquiry,
    enquiry_edit_deadline,
    get_active_correction_request,
    mark_correction_responded,
)

logger = logging.getLogger(__name__)


def _get_public_course(course_id):
    """Fetch a Course, 404ing unless it — and its college — are the same
    ones a student could actually reach by browsing the public site
    (active course, approved college). This prevents enquiries being
    submitted against inactive courses or unapproved/suspended colleges
    via a guessed URL.
    """
    return get_object_or_404(
        Course.objects.select_related("college"),
        pk=course_id,
        is_active=True,
        college__status=College.Status.APPROVED,
    )


def enquiry_create(request, course_id):
    """Admission Enquiry submission form for one specific Course.

    Uses the Post/Redirect/Get pattern (matching core.views.contact) so
    refreshing the confirmation page never resubmits the form.
    """
    course = _get_public_course(course_id)

    if request.method == "POST":
        form = EnquiryForm(request.POST, course=course)
        if form.is_valid():
            enquiry = form.save(commit=False)
            if request.user.is_authenticated and request.user.is_student:
                enquiry.submitted_by = request.user
            enquiry.save()
            logger.info(
                "Enquiry #%s submitted by %s <%s> for %s (%s)",
                enquiry.pk,
                enquiry.full_name,
                enquiry.email,
                course.course_name,
                course.college.name,
            )
            messages.success(
                request,
                "Your admission enquiry has been submitted successfully!",
            )
            return redirect("admissions:enquiry_success", pk=enquiry.pk)
    else:
        form = EnquiryForm(course=course)

    context = {"form": form, "course": course, "college": course.college}
    return render(request, "admissions/enquiry_form.html", context)


def enquiry_success(request, pk):
    """Confirmation page after a successful enquiry submission.

    Looked up without any ownership check (anonymous students have no
    account to check against), scoped only to non-deleted enquiries.
    """
    enquiry = get_object_or_404(
        Enquiry.objects.select_related("course", "college"), pk=pk
    )
    return render(request, "admissions/enquiry_success.html", {"enquiry": enquiry})


@login_required
def enquiry_self_edit(request, pk):
    """Phase 1, Feature 5 — a Student edits their own submitted enquiry,
    within the configurable edit window (or while an open Correction
    Request extends it — see admissions/services.py). Scoped to
    `submitted_by=request.user` (404 for any other enquiry, including
    another student's or an anonymous/guest submission with no owner),
    matching the "never confirm existence of something out of scope"
    pattern used everywhere else in this app.

    All editability logic is delegated to
    admissions.services.can_student_edit_enquiry — this view only
    orchestrates the GET/POST flow around whatever that function decides.
    """
    enquiry = get_object_or_404(
        Enquiry.objects.select_related("course", "college"),
        pk=pk, submitted_by=request.user,
    )
    active_correction = get_active_correction_request(enquiry)
    editable = can_student_edit_enquiry(enquiry, request.user)

    context = {
        "enquiry": enquiry,
        "editable": editable,
        "deadline": enquiry_edit_deadline(enquiry),
        "active_correction": active_correction,
    }

    if not editable:
        return render(request, "admissions/enquiry_self_edit.html", context)

    if request.method == "POST":
        form = EnquirySelfEditForm(request.POST, instance=enquiry)
        if form.is_valid():
            form.save()
            if active_correction:
                mark_correction_responded(active_correction)
            logger.info("Enquiry #%s self-edited by %s", enquiry.pk, request.user.username)
            messages.success(request, "Your enquiry has been updated.")
            return redirect("dashboard:student")
        messages.error(request, "Please correct the errors below and try again.")
    else:
        form = EnquirySelfEditForm(instance=enquiry)

    context["form"] = form
    return render(request, "admissions/enquiry_self_edit.html", context)
