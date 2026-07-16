"""
Custom user model and role profiles for Campora.

Campora uses ONE custom Django user model (accounts.User) with a `role`
field, rather than separate authentication systems per role. This is the
standard, Django-recommended approach for role-based multi-tenant apps.

Architecture (per the platform vision):

    User (role: SUPER_ADMIN | COLLEGE_ADMIN | COLLEGE_STAFF | STUDENT)
      |-- StudentProfile   (role == STUDENT)
      |-- StaffProfile     (role == COLLEGE_ADMIN or COLLEGE_STAFF; FK -> College)

SUPER_ADMIN users have no profile model — they are platform staff and are
typically also Django `is_staff`/`is_superuser` accounts managed via the
admin.

NOTE ON SCOPE: this phase defines the authentication *architecture* only
(models + admin registration). Registration forms, login views, the
approval workflow UI, and role-specific dashboards are intentionally not
built yet — per the platform vision doc: "Implementation can occur in
future phases. Only prepare the architecture now." Those arrive in later
phases (Phase 9 and beyond).
"""
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class User(AbstractUser):
    """Campora's custom user model. Adds a platform role to Django's
    built-in auth fields (username, email, password, is_staff, etc.)."""

    class Role(models.TextChoices):
        SUPER_ADMIN = "SUPER_ADMIN", "Platform Admin"
        COLLEGE_ADMIN = "COLLEGE_ADMIN", "College Admin"
        COLLEGE_STAFF = "COLLEGE_STAFF", "College Staff"
        STUDENT = "STUDENT", "Student"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
        db_index=True,
        help_text="Determines what the user can see and manage on the platform.",
    )

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_platform_admin(self):
        return self.role == self.Role.SUPER_ADMIN

    @property
    def is_college_admin(self):
        return self.role == self.Role.COLLEGE_ADMIN

    @property
    def is_college_staff_role(self):
        """Named to avoid clashing with Django's built-in `is_staff` field."""
        return self.role == self.Role.COLLEGE_STAFF

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT


class StudentProfile(models.Model):
    """Extra profile data for STUDENT-role users."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="student_profile"
    )
    phone = models.CharField(max_length=15, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Student profile: {self.user.get_full_name() or self.user.username}"

    def clean(self):
        if self.user_id and self.user.role != User.Role.STUDENT:
            raise ValidationError("A Student Profile can only be linked to a STUDENT-role user.")


class StaffProfile(models.Model):
    """Links a COLLEGE_ADMIN or COLLEGE_STAFF user to the college they work
    for. Whether a given staff member is the college's admin vs. regular
    staff is determined by `user.role`, not a separate field here — this
    avoids two sources of truth for the same distinction.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="staff_profile"
    )
    college = models.ForeignKey(
        "courses.College", on_delete=models.CASCADE, related_name="staff_members"
    )
    designation = models.CharField(
        max_length=100, blank=True, help_text="e.g. Admissions Officer, Counsellor."
    )
    phone = models.CharField(max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["college__name", "user__username"]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} @ {self.college.name}"

    def clean(self):
        if self.user_id and self.user.role not in (
            User.Role.COLLEGE_ADMIN,
            User.Role.COLLEGE_STAFF,
        ):
            raise ValidationError(
                "A Staff Profile can only be linked to a COLLEGE_ADMIN or COLLEGE_STAFF user."
            )
