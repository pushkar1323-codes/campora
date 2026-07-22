"""
Enterprise Timeline Engine — Phase 3A.

This is a USER-FACING history, not an audit log (Feature: "This Timeline
is intended for users. It is NOT an Audit Log."). Audit Logs are a
separate, later phase (3B) with different requirements (immutable
before/after values, actor, IP address, user agent) -- do not conflate
the two models when Phase 3B arrives.

Same generic-ContentType pattern as communication/staff_notes, for the
same reason: reusable by future modules (Scholarships, Placements,
Hostel, Library, Support, Faculty Communication) without redesign.
Nothing outside this app should import ContentType or touch
`content_type`/`object_id`/`content_object` directly -- every other app
talks to timeline.services.TimelineService instead. See
timeline/services.py.

Entries are immutable once created (no edit, no soft delete) -- a
Timeline is automatic history, never manually authored or corrected the
way a Staff Note is, so there is nothing here for a user to edit or
delete in the first place.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class TimelineEntry(models.Model):
    """Feature 1/2. A single automatic history entry for any object.

    `category`/`event_type` are deliberately plain CharFields, not a
    Django `choices=`-constrained enum: Feature 2 explicitly asks for
    "categories such as..." and "future modules should be able to add
    categories without redesign" -- a fixed `choices=` list would defeat
    that by requiring a migration (and touching this shared app) every
    time any future module needs a new category or event type. The
    `Category` class below documents the categories this phase actually
    uses, as a convenience constant, not a closed set.
    """

    class Category:
        """Feature 2's suggested categories. Any string is valid --
        future modules are free to introduce their own (e.g. a Hostel
        module might use "MAINTENANCE") without touching this app.
        """

        ADMISSION = "ADMISSION"
        COMMUNICATION = "COMMUNICATION"
        CORRECTION = "CORRECTION"
        VERIFICATION = "VERIFICATION"
        ASSIGNMENT = "ASSIGNMENT"
        STATUS = "STATUS"
        DOCUMENT = "DOCUMENT"
        SYSTEM = "SYSTEM"

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    category = models.CharField(max_length=30, db_index=True)
    event_type = models.CharField(
        max_length=50, db_index=True,
        help_text="Machine-readable event identifier, e.g. 'ENQUIRY_SUBMITTED'. "
                   "Domain-specific vocabulary belongs in the calling app (e.g. "
                   "admissions/services.py), not here.",
    )
    title = models.CharField(max_length=255, help_text="Feature 1: Event Title.")
    description = models.TextField(blank=True, help_text="Feature 1: Event Description.")

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="timeline_entries",
        help_text="Null for system-generated events with no human actor.",
    )
    actor_role = models.CharField(
        max_length=50, blank=True,
        help_text="Free-text snapshot of the actor's role at event time, same pattern as "
                   "communication.Message.sender_role / staff_notes.StaffNote.author_role.",
    )

    metadata = models.JSONField(default=dict, blank=True)
    icon = models.CharField(
        max_length=50, blank=True,
        help_text="Icon identifier -- a lucide-react icon name (e.g. 'file-plus', 'send', "
                   "'check-circle'), rendered directly by templates/timeline/_timeline_list.html.",
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  # Feature 1: Timestamp

    class Meta:
        ordering = ["-created_at"]  # Feature 4: "Newest entries first"
        indexes = [
            models.Index(fields=["content_type", "object_id", "created_at"]),
            models.Index(fields=["content_type", "object_id", "category"]),
        ]

    def __str__(self):
        return f"{self.title} @ {self.created_at:%Y-%m-%d %H:%M}"
