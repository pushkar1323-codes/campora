"""
Course model for Campora.

Owns the catalogue of courses that students can express interest in via
an Enquiry (see admissions.models.Enquiry). Kept intentionally simple per
DATABASE_DESIGN.docx section 4 — course content management (syllabus,
fees, seats, etc.) is out of scope unless a future phase adds it.
"""
from django.db import models


class Course(models.Model):
    """A course offered by the institution that students can enquire about."""

    course_name = models.CharField(
        max_length=150,
        unique=True,
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
        ordering = ["course_name"]

    def __str__(self):
        return self.course_name
