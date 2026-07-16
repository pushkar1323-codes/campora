"""
Forms for the admissions app — Phase 4: Admission Enquiry.

EnquiryForm is a ModelForm bound to a *specific* Course, supplied by the
view (see admissions/views.py::enquiry_create). There is deliberately no
College or Course field on the form itself: per MASTER_RULES.docx section 6
("Students must always select a College before selecting a Course" / "An
Enquiry must always reference both the selected College and the selected
Course" / "Validation must prevent selecting a Course that does not belong
to the chosen College"), the course is fixed by the URL the student arrived
from (a specific college's course card), so there is no course/college
dropdown for a student to mismatch in the first place. `Enquiry.save()`
already derives `college` from `course.college` (see admissions/models.py),
so the College is always guaranteed to be consistent by construction.
"""
from django import forms

from .models import Enquiry

_TEXT_INPUT = "form-control"
_SELECT = "form-select"


class EnquiryForm(forms.ModelForm):
    """Admission enquiry form for a single, pre-selected Course."""

    class Meta:
        model = Enquiry
        fields = [
            "full_name",
            "father_name",
            "email",
            "mobile",
            "address",
            "dob",
            "gender",
            "qualification",
            "percentage",
            "admission_year",
        ]
        widgets = {
            "full_name": forms.TextInput(attrs={
                "class": _TEXT_INPUT, "placeholder": "Student's full name",
            }),
            "father_name": forms.TextInput(attrs={
                "class": _TEXT_INPUT, "placeholder": "Father's / Guardian's name",
            }),
            "email": forms.EmailInput(attrs={
                "class": _TEXT_INPUT, "placeholder": "you@example.com",
            }),
            "mobile": forms.TextInput(attrs={
                "class": _TEXT_INPUT, "placeholder": "10-15 digit mobile number",
            }),
            "address": forms.Textarea(attrs={
                "class": _TEXT_INPUT, "rows": 3, "placeholder": "Full residential address",
            }),
            "dob": forms.DateInput(attrs={
                "class": _TEXT_INPUT, "type": "date",
            }),
            "gender": forms.Select(attrs={"class": _SELECT}),
            "qualification": forms.TextInput(attrs={
                "class": _TEXT_INPUT, "placeholder": "e.g. Class 12 / Bachelor's Degree",
            }),
            "percentage": forms.NumberInput(attrs={
                "class": _TEXT_INPUT, "step": "0.01", "min": "0", "max": "100",
                "placeholder": "0-100",
            }),
            "admission_year": forms.NumberInput(attrs={
                "class": _TEXT_INPUT, "placeholder": "e.g. 2026",
            }),
        }

    def __init__(self, *args, course=None, **kwargs):
        """`course` is required and is never taken from user input — the
        view resolves it from the URL (a specific course belonging to a
        specific, already-known college) and passes it in here.
        """
        super().__init__(*args, **kwargs)
        if course is None:
            raise ValueError("EnquiryForm requires a `course` instance.")
        self._course = course

    def save(self, commit=True):
        enquiry = super().save(commit=False)
        enquiry.course = self._course
        # enquiry.college is auto-derived from enquiry.course in
        # Enquiry.save() itself — never set independently here.
        if commit:
            enquiry.save()
        return enquiry
