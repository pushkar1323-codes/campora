"""
Reusable field validators for the admissions app.

Kept separate from models.py so they can be unit-tested independently and
reused by both Django Forms (Phase 4) and the model layer, following the
DRY principle rather than duplicating validation logic in multiple places.
"""
import re

from django.core.exceptions import ValidationError
from django.utils import timezone

MOBILE_NUMBER_PATTERN = re.compile(r"^\d{10,15}$")


def validate_mobile_number(value):
    """Mobile numbers must contain only digits, 10-15 digits long.

    Per DATABASE_DESIGN.docx section 6: "Mobile number must contain only digits."
    """
    if not MOBILE_NUMBER_PATTERN.fullmatch(value):
        raise ValidationError(
            "Enter a valid mobile number containing only digits (10-15 digits long)."
        )


def validate_dob_not_future(value):
    """Date of birth must be a past date.

    Per DATABASE_DESIGN.docx section 3/6: "DOB cannot be in the future."
    """
    if value >= timezone.localdate():
        raise ValidationError("Date of birth must be a date in the past.")


def validate_admission_year_not_past(value):
    """Admission year must be the current year or a future year.

    Per DATABASE_DESIGN.docx section 6: "Admission year cannot be in the past."
    """
    current_year = timezone.localdate().year
    if value < current_year:
        raise ValidationError(f"Admission year cannot be earlier than {current_year}.")
