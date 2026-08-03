"""
Notification Center — a reusable, platform-wide module (early / direct-call
implementation of IMPLEMENTATION_PLAN.docx Phase 4B) for surfacing "something
changed, go look" alerts to every authenticated role, without users having to
manually re-open every enquiry or conversation to find out.

Same generic-ContentType pattern as communication/staff_notes/timeline, for
the same reason: any future module (Hostel, Scholarships, Placements,
Finance, Certificates, ...) can publish a Notification against its own
object without this app knowing anything about it. Nothing outside this app
should import ContentType/GenericForeignKey directly — every caller goes
through notifications.services.NotificationService instead. See
notifications/services.py.

This is a direct-call implementation, not a pub-sub Event Bus (that
infrastructure — a dedicated Event Publisher/Dispatcher — is documented in
IMPLEMENTATION_PLAN.docx Phase 4A/4C as later, separate work). Every current
call site is a single, already-isolated function call added to an existing
state-changing function (admissions.views.enquiry_create,
communication.services.CommunicationService.post_message,
admissions.services.create_correction_request,
core.services.ContactService.create_message, the enquiry_edit status-change
hook, ...) — exactly the same "event-readiness" pattern already used
elsewhere in this project (see admissions/services.py's own module
docstring). A future Event Publisher can be introduced underneath
NotificationService.notify()/notify_many() alone, with zero change needed to
any caller.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Notification(models.Model):
    """One alert for one recipient. Deliberately per-recipient (not a
    single row fanned out at read-time) — same reasoning
    communication.ThreadParticipant uses for read status: a plain
    `is_read`/`read_at` pair per row is simpler and sufficiently scaled for
    this platform's data volumes than a shared-row + per-user-read-state
    join table.
    """

    class Priority(models.TextChoices):
        """DATABASE_DESIGN.docx section 9 ('Priority'). A genuine
        `choices=` enum (unlike `notification_type` below) since there is a
        small, fixed, UI-meaningful set of priorities — unlike event types,
        which grow with every future module.
        """

        LOW = "LOW", "Low"
        NORMAL = "NORMAL", "Normal"
        HIGH = "HIGH", "High"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications",
    )

    notification_type = models.CharField(
        max_length=50, db_index=True,
        help_text="Machine-readable event identifier, e.g. 'STAFF_REPLIED', "
                   "'ENQUIRY_ADMITTED'. Deliberately a plain CharField, not choices= "
                   "— same reasoning as timeline.TimelineEntry.event_type — so future "
                   "modules add new notification types without a migration.",
    )
    title = models.CharField(max_length=255)
    body = models.CharField(max_length=500, blank=True)

    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)

    action_url = models.CharField(
        max_length=500, blank=True,
        help_text="Precomputed deep-link (e.g. the enquiry detail page), supplied by the "
                   "caller who already knows what kind of object this is about — avoids "
                   "teaching this app owner-type-dispatch logic the way "
                   "dashboard.views._thread_owner_detail_url needed for Communication.",
    )

    # Optional generic link to the object this notification is about —
    # for future features (e.g. "show me every notification about this
    # enquiry"), not required for basic display (action_url already covers
    # that).
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    college = models.ForeignKey(
        "courses.College", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="notifications",
        help_text="Optional, caller-supplied — same reasoning as "
                   "timeline.TimelineEntry.college / audit.AuditLog.college — for "
                   "efficient college-scoped queries later. This app has no idea what "
                   "'college' means for any given object type; only the calling code "
                   "does. SET_NULL, not CASCADE, so a college's own removal never takes "
                   "a user's notification history down with it.",
    )

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"]),
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.title} -> {self.recipient} @ {self.created_at:%Y-%m-%d %H:%M}"
