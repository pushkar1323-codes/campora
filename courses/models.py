"""
College and Course models for Campora.

Architecture: College (1) -> (*) Course (1) -> (*) Enquiry [admissions app].

College is intentionally kept in this app rather than a new `colleges` app:
it is the direct parent of Course, keeping the catalogue (colleges +
their courses) in one modular, cohesive app without fragmenting further.
"""
from django.db import models
from django.utils.text import slugify


class College(models.Model):
    """A college registered on the Campora platform.

    `status` prepares the architecture for the College Registration /
    Approval Workflow described in the platform vision. Only APPROVED
    colleges (and their courses) are shown on the public website; the
    actual self-service registration form and Super Admin approval UI are
    built in a later phase — this phase only lays the data-model
    groundwork, per the platform vision's "prepare the architecture now"
    instruction.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending Approval"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        SUSPENDED = "SUSPENDED", "Suspended"

    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    logo = models.ImageField(upload_to="colleges/logos/", blank=True, null=True)
    cover_image = models.ImageField(upload_to="colleges/covers/", blank=True, null=True)
    short_description = models.CharField(
        max_length=255, blank=True, help_text="One-line summary shown on college cards."
    )
    description = models.TextField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True, db_index=True)
    state = models.CharField(max_length=100, blank=True, db_index=True)
    phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def is_public(self):
        """Only approved colleges (and by extension their courses) appear
        on the public-facing website."""
        return self.status == self.Status.APPROVED

    @property
    def active_course_count(self):
        return self.courses.filter(is_active=True).count()


class Course(models.Model):
    """A course offered by a specific College."""

    college = models.ForeignKey(
        College, on_delete=models.CASCADE, related_name="courses"
    )
    course_name = models.CharField(
        max_length=150,
        help_text="Full display name of the course, e.g. 'B.Tech Computer Science'.",
    )
    duration = models.CharField(
        max_length=50,
        help_text="Human-readable duration, e.g. '4 Years' or '18 Months'.",
    )
    eligibility = models.CharField(
        max_length=255,
        help_text="Minimum eligibility criteria for admission to this course.",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Inactive courses are hidden from the public site but preserved for historical enquiries.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["college__name", "course_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["college", "course_name"], name="unique_course_name_per_college"
            ),
        ]

    def __str__(self):
        return f"{self.course_name} ({self.college.name})"
