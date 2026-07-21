"""
Internal Staff Notes — Phase 2B.

Deliberately a SEPARATE module from `communication` (per this phase's own
objective: "The Communication System and Internal Staff Notes are two
completely separate features"), even though it reuses the same
architectural pattern: a generic (content_type, object_id) relation so
this app isn't tied to `admissions.Enquiry` and can be reused by future
modules (Scholarships, Placements, Hostel, Library, Faculty
Communication, Support Tickets, Document Verification) without redesign
— Feature 11.

Same encapsulation rule as communication/models.py: nothing outside this
app should import ContentType or touch `content_type`/`object_id`/
`content_object` directly. Every other app talks to
staff_notes.services.StaffNoteService instead, passing a plain model
instance. See staff_notes/services.py.

Unlike communication.MessageThread/Message, there's no "thread" wrapper
here — a StaffNote attaches directly to its owner object. Notes aren't a
back-and-forth conversation the way messages are; a flat, per-object list
is the right shape, and keeping it flat (no extra join to a Thread model)
is simpler for something that's always private to staff anyway.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class StaffNote(models.Model):
    """Feature 2. A single private staff note on any object.

    `metadata` (JSONField) is the same deliberately-generic extension
    point communication.Message uses — e.g. a future structured tag or
    category, without a schema change here.
    """

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="staff_notes_authored",
    )
    author_role = models.CharField(
        max_length=50, blank=True,
        help_text="Free-text snapshot of the author's role at creation time (e.g. 'College Staff', "
                   "'College Admin') so a later role change never rewrites note history.",
    )
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    is_edited = models.BooleanField(default=False)

    # Feature 3: soft delete + restore, never a hard delete through the
    # application. deleted_at/deleted_by/restored_at/restored_by give the
    # same auditability communication.Message's soft delete does.
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="staff_notes_deleted",
    )
    restored_at = models.DateTimeField(null=True, blank=True)
    restored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="staff_notes_restored",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]  # most recent note first
        indexes = [
            models.Index(fields=["content_type", "object_id", "is_deleted"]),
            models.Index(fields=["content_type", "object_id", "created_at"]),
        ]
        # Feature 7 ("search-ready", not "search implemented"): same
        # reasoning as communication.Message.Meta -- `content` is a
        # TextField, and MySQL/InnoDB (this project's production engine)
        # refuses a plain index on a full TEXT column without an explicit
        # key-length prefix. Deferred to whichever future phase actually
        # builds search.

    def __str__(self):
        who = self.author or "Unknown"
        return f"Note by {who} @ {self.created_at:%Y-%m-%d %H:%M}"
