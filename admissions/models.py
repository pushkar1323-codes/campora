"""
Enquiry model for Campora — the core admission enquiry record.

See DATABASE_DESIGN.docx section 3 for the authoritative field list, and
PROJECT_BRAIN.docx "Enquiry Workflow" for the status lifecycle.
"""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from courses.models import Course

from .validators import (
    validate_admission_year_not_past,
    validate_dob_not_future,
    validate_mobile_number,
)


class EnquiryQuerySet(models.QuerySet):
    """Custom queryset so soft-delete filtering reads clearly at call sites."""

    def active(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)


class EnquiryManager(models.Manager):
    """Default manager: excludes soft-deleted enquiries.

    This is the standard Django soft-delete pattern — every ordinary query
    (`Enquiry.objects.all()`, `Enquiry.objects.filter(...)`, admin list views,
    dashboard counts, etc.) automatically excludes deleted records, so no
    call site has to remember to add `is_deleted=False` by hand. Code that
    genuinely needs deleted rows (the Recycle Bin, Phase 8) uses
    `Enquiry.all_objects` explicitly instead.
    """

    def get_queryset(self):
        return EnquiryQuerySet(self.model, using=self._db).active()


class Enquiry(models.Model):
    """A prospective student's admission enquiry."""

    class Gender(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"
        OTHER = "O", "Other"

    class Status(models.TextChoices):
        """Workflow stages per PROJECT_BRAIN.docx "Enquiry Workflow"."""

        NEW = "NEW", "New"
        CONTACTED = "CONTACTED", "Contacted"
        INTERESTED = "INTERESTED", "Interested"
        DOCUMENTS_PENDING = "DOCUMENTS_PENDING", "Documents Pending"
        INTERVIEW_SCHEDULED = "INTERVIEW_SCHEDULED", "Interview Scheduled"
        FEE_PENDING = "FEE_PENDING", "Fee Pending"
        ADMITTED = "ADMITTED", "Admitted"
        REJECTED = "REJECTED", "Rejected"

    full_name = models.CharField(max_length=100)
    father_name = models.CharField(max_length=100)
    email = models.EmailField(db_index=True)
    mobile = models.CharField(
        max_length=15, validators=[validate_mobile_number], db_index=True
    )
    address = models.TextField()
    dob = models.DateField(
        verbose_name="Date of Birth", validators=[validate_dob_not_future]
    )
    gender = models.CharField(max_length=1, choices=Gender.choices)
    qualification = models.CharField(
        max_length=100, help_text="Highest qualification completed."
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Academic percentage, 0-100.",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name="enquiries",
        help_text="Course the student is interested in.",
    )
    admission_year = models.PositiveIntegerField(
        validators=[validate_admission_year_not_past], db_index=True
    )
    status = models.CharField(
        max_length=25, choices=Status.choices, default=Status.NEW, db_index=True
    )
    staff_notes = models.TextField(
        blank=True, help_text="Internal notes visible to staff only."
    )
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EnquiryManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name_plural = "Enquiries"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "admission_year"]),
            models.Index(fields=["is_deleted", "status"]),
        ]

    def __str__(self):
        return f"{self.full_name} — {self.course.course_name}"

    def soft_delete(self):
        """Mark this enquiry as deleted without removing it from the database."""
        self.is_deleted = True
        self.save(update_fields=["is_deleted", "updated_at"])

    def restore(self):
        """Undo a soft delete."""
        self.is_deleted = False
        self.save(update_fields=["is_deleted", "updated_at"])
