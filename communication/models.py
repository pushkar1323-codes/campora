"""
Enterprise Communication System — Phase 2A.

Deliberately NOT coupled to admissions.Enquiry (or any other specific
model). A MessageThread attaches to *any* Django model instance via a
generic (content_type, object_id) pair, so this app can be reused as-is
for Hostel, Scholarships, Placements, Faculty Communication, Support
Tickets, Document Verification, etc. — future modules request a thread
for their own object and get one, with zero changes here.

IMPORTANT: nothing outside this app should import ContentType or touch
`content_type`/`object_id`/`content_object` directly — that's the whole
point of keeping GenericForeignKey usage internal to this module. Every
other app talks to communication.services.CommunicationService instead,
passing a plain model instance (e.g. an Enquiry) and letting the service
resolve the generic relation. See communication/services.py.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class MessageThread(models.Model):
    """One thread per "owner" object (Feature 1: "Each Admission Enquiry
    should have a dedicated communication thread" — generalized to "each
    object of any type gets a dedicated thread").
    """

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # One thread per object — CommunicationService.create_thread_if_missing()
        # is the only supported way to obtain one, and relies on this
        # constraint to make "get or create" race-safe.
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id"], name="unique_thread_per_object"
            )
        ]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"Thread for {self.content_type.app_label}.{self.content_type.model} #{self.object_id}"


class ThreadParticipant(models.Model):
    """Feature (architectural improvement #2): who is part of a thread.

    Deliberately generic — NOT hard-coded to "one student + one staff
    member". Today only a Student and whichever College Staff/Admin have
    engaged with an enquiry's thread are added (see
    CommunicationService.post_message / admissions/dashboard views), but
    a future module (Hostel Warden, Placement Officer, Finance, a second
    student on a shared application, ...) can be added as a participant
    without any schema change — just another row here.

    `role_label` is deliberately a free string, not a choices field tied
    to accounts.User.Role — those role names (COLLEGE_STAFF, ...) are
    admissions-domain vocabulary; a future Hostel module's participants
    might be "Warden" or "Maintenance Staff", which this app has no
    business knowing about in advance.
    """

    thread = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="thread_participations")
    role_label = models.CharField(
        max_length=50, blank=True,
        help_text="Free-text snapshot of this participant's role, e.g. 'Student', 'College Staff'.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="False if this participant has been removed from the thread, without deleting the row.",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["thread", "user"], name="unique_participant_per_thread")
        ]
        indexes = [
            models.Index(fields=["thread", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user} in {self.thread} ({self.role_label or 'participant'})"


class Message(models.Model):
    """Feature 2. A single message in a thread.

    `metadata` (JSONField) is the primary, deliberately-generic extension
    point (architectural improvement #8) — e.g. a future attachment
    reference, a correction-request id, or any other structured detail a
    message type wants to carry, without a schema change here. See
    Message.Type below and CommunicationService.post_system_message.
    """

    class Type(models.TextChoices):
        """Feature 3. Only USER/SYSTEM/CORRECTION_REQUEST are wired up
        this phase, per the spec ("Initially implement: USER, SYSTEM,
        CORRECTION_REQUEST"). Adding STATUS_UPDATE/NOTIFICATION later is a
        one-line addition to this enum plus whatever future phase wires
        them up — deliberately not pre-added as unused values now.
        """

        USER = "USER", "User"
        SYSTEM = "SYSTEM", "System"
        CORRECTION_REQUEST = "CORRECTION_REQUEST", "Correction Request"

    thread = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="sent_messages",
        help_text="Null for system-generated messages (message_type=SYSTEM/CORRECTION_REQUEST).",
    )
    sender_role = models.CharField(
        max_length=50, blank=True,
        help_text="Free-text snapshot of the sender's role at send time (e.g. 'Student', 'College Staff', "
                   "'System') so a later role change never rewrites message history.",
    )
    message_type = models.CharField(max_length=30, choices=Type.choices, default=Type.USER, db_index=True)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    is_edited = models.BooleanField(default=False)

    # Feature 7: soft delete only — never a hard delete. Architectural
    # improvement #3 adds deleted_at/deleted_by for auditability on top
    # of the plain is_deleted flag the spec asked for.
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="deleted_messages",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]  # Feature 1: "displayed chronologically"
        indexes = [
            models.Index(fields=["thread", "created_at"]),
            models.Index(fields=["thread", "is_read", "is_deleted"]),
        ]
        # Feature 9 ("search-ready", not "search implemented"): `content`
        # is a TextField, and MySQL/InnoDB (this project's production
        # engine — see DATABASE_DESIGN.docx) refuses a plain index on a
        # full TEXT column without an explicit key-length prefix. Adding
        # one now, before there's an actual search feature to size it
        # for, would be guessing. CommunicationService.search_messages()
        # below does a plain `icontains` scan today; a real full-text
        # index (MySQL FULLTEXT, or a prefix index) is a one-time,
        # additive migration to add if/when Feature 9 is actually built.

    def __str__(self):
        who = self.sender or "System"
        return f"Message from {who} in {self.thread} @ {self.created_at:%Y-%m-%d %H:%M}"

    @property
    def is_system_generated(self):
        return self.message_type in (self.Type.SYSTEM, self.Type.CORRECTION_REQUEST)
