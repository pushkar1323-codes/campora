from django.conf import settings
from django.db import models


class ContactMessage(models.Model):
    """A message submitted through the public 'Contact Us' page
    (core/forms.py::ContactForm). Distinct from admissions.Enquiry (a
    course-specific admission request) and from the communication app's
    Message (a threaded conversation tied to an existing object) --
    this is a one-off, platform-level message from anyone (anonymous or
    logged in) to the Platform Admin team.

    Previously this form validated and logged the submission but never
    persisted it anywhere, so it was never actually visible to any
    administrator despite appearing to succeed from the visitor's side.
    This model, and core/services.py::ContactService built on it, fix
    that: every submission is now saved and reviewable in the Campora
    Admin Panel and a dedicated Platform Admin dashboard page.
    """

    class Status(models.TextChoices):
        NEW = "NEW", "New"
        READ = "READ", "Read"
        RESOLVED = "RESOLVED", "Resolved"

    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15, blank=True)
    subject = models.CharField(max_length=150)
    message = models.TextField()

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="contact_messages",
        help_text="The logged-in user who submitted this, if any -- null for an anonymous visitor.",
    )

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    read_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="contact_messages_read",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="contact_messages_resolved",
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.subject} — {self.full_name} ({self.get_status_display()})"
