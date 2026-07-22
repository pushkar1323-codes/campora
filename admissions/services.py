"""
Admission-workflow business rules for Campora — Phase 1 (Secure Admission
Workflow).

Centralizing these rules here, rather than in models or views, means:
  - views and forms stay thin and only orchestrate;
  - the same rule (e.g. "can this student edit this enquiry right now?")
    is enforced identically everywhere it's checked — the view that gates
    access and the template that decides whether to show a form both call
    the same function, so they can never silently disagree;
  - the rules are unit-testable in isolation from HTTP/views.

Every rule that affects *behaviour* (edit-window duration, whether a
correction request extends that window) is read from
`django.conf.settings` rather than hard-coded, so it can be changed via
configuration alone — see config/settings.py's "Admission Workflow"
section — without touching this code.

Event readiness (for future Phase 4B/4C Notification/Timeline/Audit
subscribers): every state-changing function below performs its change via
a normal Django `.save()` or `.create()` call, which already dispatches
`django.db.models.signals.post_save` on every invocation. A future
subscriber can attach a `post_save` receiver to `CorrectionRequest` (and,
for the enquiry self-edit, to `Enquiry`) to react to this activity —
sending a notification, writing a timeline entry, writing an audit
record — without any change to this module or its callers. Nothing here
needs to be refactored to make that possible.
"""
import logging

from django.conf import settings
from django.utils import timezone

from communication.models import Message
from communication.services import CommunicationService
from timeline.models import TimelineEntry
from timeline.services import TimelineService

from .models import CorrectionRequest, Enquiry

logger = logging.getLogger(__name__)


def get_edit_window_minutes():
    """How long, in minutes, after submission a student may edit their own
    enquiry (Feature 5). Configurable via settings.ENQUIRY_EDIT_WINDOW_MINUTES
    / the ENQUIRY_EDIT_WINDOW_MINUTES environment variable. Default: 30.
    """
    return getattr(settings, "ENQUIRY_EDIT_WINDOW_MINUTES", 30)


def correction_extends_edit_window():
    """Whether an open Correction Request lets a student edit past their
    normal edit window (Feature 6). A configurable business rule — see
    settings.CORRECTION_REQUEST_EXTENDS_EDIT_WINDOW — not a hard-coded
    exception in code. Default: True (a correction request only exists
    because staff decided something needs fixing, so blocking the student
    from actually fixing it would make the workflow unusable).
    """
    return getattr(settings, "CORRECTION_REQUEST_EXTENDS_EDIT_WINDOW", True)


def enquiry_edit_deadline(enquiry):
    """The moment after which the standard edit window closes for this
    enquiry, independent of any correction request."""
    return enquiry.created_at + timezone.timedelta(minutes=get_edit_window_minutes())


def is_within_edit_window(enquiry):
    """True while `enquiry` is still inside its standard edit window."""
    return timezone.now() <= enquiry_edit_deadline(enquiry)


def get_active_correction_request(enquiry):
    """The enquiry's current unresolved Correction Request, if any (most
    recent first, in case more than one was ever opened)."""
    return (
        enquiry.correction_requests
        .filter(status__in=[CorrectionRequest.Status.OPEN, CorrectionRequest.Status.RESPONDED])
        .order_by("-created_at")
        .first()
    )


def can_student_edit_enquiry(enquiry, user):
    """The single source of truth for "can this logged-in user edit this
    enquiry right now" (Feature 5 + Feature 7's "Student: edit own enquiry
    during edit window"). Used identically by the view (to gate access)
    and the template (to decide whether to render the form or a locked
    message) — see admissions/views.py::enquiry_self_edit.
    """
    if not user.is_authenticated or enquiry.submitted_by_id != user.id:
        return False
    if is_within_edit_window(enquiry):
        return True
    if correction_extends_edit_window() and get_active_correction_request(enquiry):
        return True
    return False


def can_staff_edit_personal_fields(user):
    """Feature 2 / Feature 7 permission matrix: only a Platform Admin may
    directly edit an enquiry's personal-information snapshot. This is
    also the sole correction path for an anonymous/guest enquiry (no
    logged-in student, so there is no account for a Correction Request to
    reach) — Platform Admin's "full access" override covers that case.
    College Admin and College Staff never get this; they use
    create_correction_request() below instead.
    """
    return bool(getattr(user, "is_authenticated", False) and user.is_platform_admin)


def create_correction_request(enquiry, requested_by, reason, message=""):
    """Feature 6: staff asks the student to fix something, instead of
    editing the student's information directly.

    Phase 2A wiring: also posts a CORRECTION_REQUEST-typed system message
    into the enquiry's communication thread, via CommunicationService —
    this module never touches communication's models/ContentType
    directly (see communication/services.py's own module docstring).
    This is the one concrete "system message" trigger built this phase
    (see PROMPTS_PART_3/Phase 2A's own scope note excluding a full
    Enquiry-lifecycle event system for now):

        CorrectionRequest -> CommunicationService.post_system_message() -> (future) Event Publisher

    A future Event Publisher can be added by having post_system_message()
    itself additionally publish an event — nothing here needs to change
    for that.
    """
    correction = CorrectionRequest.objects.create(
        enquiry=enquiry, requested_by=requested_by, reason=reason, message=message,
    )
    logger.info(
        "Correction requested on Enquiry #%s by %s: %s",
        enquiry.pk, requested_by.username, reason,
    )
    system_message = f"A correction was requested: {reason}"
    if message:
        system_message += f" — {message}"
    CommunicationService.post_system_message(
        enquiry,
        content=system_message,
        message_type=Message.Type.CORRECTION_REQUEST,
        metadata={"correction_request_id": correction.pk},
    )
    TimelineService.log_event(
        enquiry,
        category=TimelineEntry.Category.CORRECTION,
        event_type="CORRECTION_REQUESTED",
        title="Correction Requested",
        description=reason,
        actor=requested_by, icon="alert-triangle",
        metadata={"correction_request_id": correction.pk},
    )
    return correction


def mark_correction_responded(correction_request):
    """Called when the student saves an edit to their enquiry while a
    Correction Request is still open — moves it to RESPONDED so staff know
    it's ready for review. Never auto-resolves (Feature 6 explicitly: "Do
    not automatically approve corrections") — a human must call
    resolve_correction_request() below.
    """
    correction_request.status = CorrectionRequest.Status.RESPONDED
    correction_request.responded_at = timezone.now()
    correction_request.save(update_fields=["status", "responded_at", "updated_at"])
    logger.info(
        "Correction request #%s marked responded (Enquiry #%s)",
        correction_request.pk, correction_request.enquiry_id,
    )
    return correction_request


def resolve_correction_request(correction_request, resolved_by):
    """Staff confirms the student's update addressed the request."""
    correction_request.status = CorrectionRequest.Status.RESOLVED
    correction_request.resolved_by = resolved_by
    correction_request.resolved_at = timezone.now()
    correction_request.save(
        update_fields=["status", "resolved_by", "resolved_at", "updated_at"]
    )
    logger.info(
        "Correction request #%s resolved by %s (Enquiry #%s)",
        correction_request.pk, resolved_by.username, correction_request.enquiry_id,
    )
    TimelineService.log_event(
        correction_request.enquiry,
        category=TimelineEntry.Category.CORRECTION,
        event_type="CORRECTION_RESOLVED",
        title="Correction Resolved",
        description=correction_request.reason,
        actor=resolved_by, icon="check-circle",
        metadata={"correction_request_id": correction_request.pk},
    )
    return correction_request
