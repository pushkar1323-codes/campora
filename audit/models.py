"""
Enterprise Audit Logging Engine — Phase 3B.

Unlike timeline.TimelineEntry (a user-facing history), AuditLog is an
administrative record for security, accountability, compliance, and
troubleshooting. Two concrete architectural consequences follow from
that:

1. IMMUTABLE (Feature 5). Enforced at three layers, deliberately
   redundant ("Protect through server-side validation"):
     a. AuditLog.save() raises if the row already has a pk (i.e. this
        would be an UPDATE, not an INSERT).
     b. AuditLog.delete() always raises.
     c. The custom manager below also blocks queryset-level
        .update()/.delete() -- Django's bulk QuerySet.update()/delete()
        do NOT go through an instance's save()/delete(), so (a) and (b)
        alone would leave a real gap.
   "Only database administrators may remove records directly" (Feature
   5) means exactly that: direct DB access outside the application, not
   anything reachable through this model, a view, the admin, or the ORM.

2. NO GenericForeignKey to the target object (unlike communication/
   staff_notes/timeline). Feature 6 explicitly warns: "Never depend
   solely on foreign keys" -- if the target object (or, in principle,
   even its ContentType, or the app that defined it) is later removed,
   a live GenericForeignKey could break or silently orphan the log
   entry. Instead, `target_model`/`object_id`/`object_display_name` are
   plain, disconnected values captured at logging time -- a *record* of
   what the target was, not a *reference* to it that depends on it still
   existing. `snapshot_data` carries a deeper point-in-time copy of
   whatever fields the calling code considers meaningful, for exactly
   the scenarios Feature 6 names (course deleted, student archived,
   enquiry removed, staff deleted).
"""
from django.conf import settings
from django.db import models


class ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("AuditLog records are immutable and cannot be bulk-updated.")

    def delete(self):
        raise ValueError(
            "AuditLog records cannot be deleted through the application. "
            "Only direct database administration may remove them."
        )


class AuditLog(models.Model):
    """Feature 1. One immutable administrative record."""

    class Severity(models.TextChoices):
        """Feature 3. A small, stable, universal severity scale (the
        same four levels as standard logging frameworks) -- unlike
        Timeline's category/event_type or this model's own `action`/
        `event_source` below, a 5th severity level is not the kind of
        thing any future module would plausibly need to invent, so a
        real `choices=`-constrained enum is the right fit here.
        """

        INFO = "INFO", "Info"
        WARNING = "WARNING", "Warning"
        ERROR = "ERROR", "Error"
        CRITICAL = "CRITICAL", "Critical"

    # -- When / What / How severe --------------------------------------
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  # Timestamp
    action = models.CharField(
        max_length=100, db_index=True,
        help_text="Action Name -- machine-readable, e.g. 'ENQUIRY_STATUS_CHANGED'.",
    )
    action_category = models.CharField(
        max_length=50, db_index=True, blank=True,
        help_text="Feature 2 grouping (e.g. 'Authentication', 'Admission', 'College Management'). "
                   "Plain text, not a choices enum -- 'future modules should easily register new "
                   "actions' without a migration, same reasoning as timeline.TimelineEntry.category.",
    )
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.INFO, db_index=True)
    event_source = models.CharField(
        max_length=30, db_index=True, blank=True,
        help_text="Feature 4, e.g. 'Web', 'Admin Panel', 'API', 'System', 'Background Job'. Plain "
                   "text for the same forward-compatibility reason as action_category.",
    )

    # -- Who --------------------------------------------------------------
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="audit_logs", help_text="Null for system/background-job-generated entries.",
    )
    actor_role = models.CharField(max_length=50, blank=True)
    college = models.ForeignKey(
        "courses.College", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="audit_logs",
        help_text="A real FK (not a snapshot string) for efficient college-scoped querying "
                   "(Feature 9) -- SET_NULL, not CASCADE, so a college's own removal can never "
                   "take its audit history down with it.",
    )

    # -- What was affected (Feature 6: survives the target's own deletion) --
    target_model = models.CharField(
        max_length=100, blank=True,
        help_text="e.g. 'admissions.Enquiry' -- a plain label, deliberately not a ContentType FK. "
                   "See module docstring.",
    )
    object_id = models.CharField(max_length=64, blank=True)
    object_display_name = models.CharField(max_length=255, blank=True)

    # -- State captured at event time --------------------------------------
    previous_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    snapshot_data = models.JSONField(default=dict, blank=True)

    # -- Request context ----------------------------------------------------
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    objects = ImmutableQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["action_category", "created_at"]),
            models.Index(fields=["college", "created_at"]),
            models.Index(fields=["target_model", "object_id"]),
            models.Index(fields=["severity", "created_at"]),
        ]

    def __str__(self):
        return f"[{self.severity}] {self.action} @ {self.created_at:%Y-%m-%d %H:%M}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("AuditLog records are immutable and cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError(
            "AuditLog records cannot be deleted through the application. "
            "Only direct database administration may remove them."
        )
