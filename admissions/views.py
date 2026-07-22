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
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from communication import permissions as comm_permissions
from communication.forms import MessageEditForm, MessageForm
from communication.models import Message
from communication.services import CommunicationService
from courses.models import College, Course
from timeline.models import TimelineEntry
from timeline.services import TimelineService

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
            TimelineService.log_event(
                enquiry,
                category=TimelineEntry.Category.ADMISSION,
                event_type="ENQUIRY_SUBMITTED",
                title="Enquiry Submitted",
                description=f"Enquiry submitted for {course.course_name} at {course.college.name}.",
                actor=enquiry.submitted_by,
                icon="file-plus",
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
                TimelineService.log_event(
                    enquiry,
                    category=TimelineEntry.Category.CORRECTION,
                    event_type="CORRECTION_SUBMITTED",
                    title="Correction Submitted",
                    description=f"Student updated their enquiry in response to: {active_correction.reason}",
                    actor=request.user, icon="check-check",
                    metadata={"correction_request_id": active_correction.pk},
                )
            logger.info("Enquiry #%s self-edited by %s", enquiry.pk, request.user.username)
            messages.success(request, "Your enquiry has been updated.")
            return redirect("dashboard:student")
        messages.error(request, "Please correct the errors below and try again.")
    else:
        form = EnquirySelfEditForm(instance=enquiry)

    context["form"] = form
    return render(request, "admissions/enquiry_self_edit.html", context)


@login_required
def enquiry_conversation(request, pk):
    """Phase 2A, Feature 1/10 — a Student views/replies in their own
    enquiry's communication thread. Ownership-scoped exactly like
    enquiry_self_edit (submitted_by=request.user, 404 for anyone else's
    enquiry) — that scoping is this view's entire domain-level
    authorization; it then explicitly makes the (now-authorized) student
    an active thread participant via CommunicationService.add_participant,
    which is what lets communication.permissions.can_view_thread /
    can_send_message pass for them afterwards. See
    communication/permissions.py's module docstring for the full
    two-tier reasoning.
    """
    enquiry = get_object_or_404(
        Enquiry.objects.select_related("course", "college"),
        pk=pk, submitted_by=request.user,
    )
    CommunicationService.add_participant(enquiry, request.user, role_label=request.user.get_role_display())
    CommunicationService.mark_thread_read(enquiry, request.user)

    if request.method == "POST":
        form = MessageForm(request.POST)
        if comm_permissions.can_send_message(request.user, enquiry) and form.is_valid():
            CommunicationService.post_message(
                enquiry, sender=request.user, content=form.cleaned_data["content"],
                sender_role=request.user.get_role_display(),
            )
            TimelineService.log_event(
                enquiry,
                category=TimelineEntry.Category.COMMUNICATION,
                event_type="STUDENT_REPLIED",
                title="Student Replied",
                actor=request.user, icon="message-square",
            )
            messages.success(request, "Message sent.")
            return redirect("admissions:enquiry_conversation", pk=enquiry.pk)
        messages.error(request, "Message cannot be empty.")
    else:
        form = MessageForm()

    context = {
        "enquiry": enquiry,
        "messages_list": CommunicationService.get_messages(enquiry),
        "message_form": form,
        "reply_url": reverse("admissions:enquiry_conversation", args=[enquiry.pk]),
    }
    return render(request, "admissions/enquiry_conversation.html", context)


def _get_own_message_or_404(request, pk):
    """Shared lookup for the student-facing message_edit/message_delete
    views below: ownership is checked via the thread's owner object's
    own `submitted_by` — domain knowledge that belongs here in admissions,
    never inside the communication app itself (see
    communication/permissions.py's module docstring).
    """
    message = get_object_or_404(
        Message.objects.select_related("thread", "sender"), pk=pk, is_deleted=False,
    )
    owner = message.thread.content_object
    if getattr(owner, "submitted_by_id", None) != request.user.id:
        raise Http404("No message matches the given query.")
    return message, owner


@login_required
def message_edit(request, pk):
    """Phase 2A, Feature 6 — a Student edits their own message. Ownership
    of the *enquiry* is checked here (domain-specific); whether *this
    particular message* may be edited is delegated to
    communication.permissions.can_edit_message (generic: sender-only,
    USER type, not deleted).
    """
    message, owner = _get_own_message_or_404(request, pk)
    if not comm_permissions.can_edit_message(request.user, message):
        raise Http404("No message matches the given query.")

    cancel_url = reverse("admissions:enquiry_conversation", args=[owner.pk])

    if request.method == "POST":
        form = MessageEditForm(request.POST, instance=message)
        if form.is_valid():
            CommunicationService.edit_message(message, form.cleaned_data["content"], edited_by=request.user)
            messages.success(request, "Message updated.")
            return redirect(cancel_url)
    else:
        form = MessageEditForm(instance=message)

    return render(request, "communication/message_edit.html", {"form": form, "cancel_url": cancel_url})


@login_required
def message_delete(request, pk):
    """Phase 2A, Feature 7 — a Student soft-deletes their own message."""
    message, owner = _get_own_message_or_404(request, pk)
    if not comm_permissions.can_delete_message(request.user, message):
        raise Http404("No message matches the given query.")

    if request.method == "POST":
        CommunicationService.delete_message(message, deleted_by=request.user)
        messages.success(request, "Message deleted.")
    return redirect("admissions:enquiry_conversation", pk=owner.pk)


@login_required
def enquiry_timeline(request, pk):
    """Phase 3A, Feature 5 — a Student views their own enquiry's
    Timeline. Ownership-scoped exactly like enquiry_self_edit/
    enquiry_conversation (submitted_by=request.user, 404 for anyone
    else's enquiry) -- that scoping IS the entire authorization for this
    view; see timeline/services.py's module docstring for why no
    additional generic permission layer is needed on top of it (Timeline
    is read-only, there's no edit/delete/restore role matrix the way
    Staff Notes has).
    """
    enquiry = get_object_or_404(
        Enquiry.objects.select_related("course", "college"),
        pk=pk, submitted_by=request.user,
    )
    context = {
        "enquiry": enquiry,
        "timeline_entries": TimelineService.get_timeline(enquiry),
    }
    return render(request, "admissions/enquiry_timeline.html", context)
