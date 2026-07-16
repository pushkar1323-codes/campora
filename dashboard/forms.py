"""
Forms for the dashboard app — Phase 6: Search, Filter & Sorting.

EnquiryFilterForm is a plain (non-Model) Form bound to request.GET, used
by dashboard.views.enquiry_list to search, filter and sort the Phase 5
enquiry listing. See PROMPTS_PART_2.docx Phase 6 for the exact required
search/filter/sort fields.
"""
from django import forms

from admissions.models import Enquiry
from courses.models import College, Course

SORT_CHOICES = [
    ("submitted", "Submission Date"),
    ("student", "Student Name"),
    ("college", "College"),
    ("course", "Course"),
]

DIR_CHOICES = [
    ("desc", "Descending"),
    ("asc", "Ascending"),
]

# Maps a public "sort" query value to the actual ORM field(s) to order by.
SORT_FIELD_MAP = {
    "student": "full_name",
    "college": "college__name",
    "course": "course__course_name",
    "submitted": "created_at",
}


class EnquiryFilterForm(forms.Form):
    """Search/filter/sort controls for the enquiry listing.

    Every field is optional. This form is bound directly to the request's
    querystring, which is user-editable and can contain stale or malformed
    values (e.g. an old bookmarked link, or a hand-edited URL) — so a bad
    value in any one field must never break the page. Django's per-field
    cleaning already gives us this for free: `cleaned_data` only contains
    the fields that individually validated successfully, regardless of
    whether the form as a whole is "valid" — callers should read filters
    via `cleaned_data.get(...)` rather than gating on `is_valid()`.
    """

    q = forms.CharField(required=False, label="Search")
    college = forms.ModelChoiceField(
        queryset=College.objects.none(), required=False, label="College"
    )
    course = forms.ModelChoiceField(
        queryset=Course.objects.none(), required=False, label="Course"
    )
    gender = forms.ChoiceField(
        choices=[("", "All Genders")] + list(Enquiry.Gender.choices),
        required=False,
    )
    status = forms.ChoiceField(
        choices=[("", "All Statuses")] + list(Enquiry.Status.choices),
        required=False,
    )
    admission_year = forms.IntegerField(required=False, label="Admission Year")
    sort = forms.ChoiceField(choices=SORT_CHOICES, required=False)
    dir = forms.ChoiceField(choices=DIR_CHOICES, required=False)

    def __init__(self, *args, staff_college=None, **kwargs):
        """`staff_college`: pass the College of a logged-in College
        Admin/Staff user to scope this form to "college ownership" rules
        — the same rule the rest of the app follows, applied here too:

        - The `college` field is removed entirely. A College Admin/Staff
          user's scope is always their own college, decided server-side in
          the view — never something they could override via the
          querystring.
        - The `course` field's choices are restricted to that college's
          courses only, so a crafted `?course=<id>` for another college's
          course simply matches nothing (never leaks another college's
          course list, never lets them filter into another college).

        With `staff_college=None` (Platform Admin), both fields cover
        every college/course on the platform.
        """
        super().__init__(*args, **kwargs)
        if staff_college is not None:
            del self.fields["college"]
            self.fields["course"].queryset = Course.objects.filter(
                college=staff_college
            ).order_by("course_name")
        else:
            self.fields["college"].queryset = College.objects.order_by("name")
            self.fields["course"].queryset = Course.objects.select_related(
                "college"
            ).order_by("college__name", "course_name")
            self.fields["course"].label_from_instance = (
                lambda course: f"{course.course_name} ({course.college.name})"
            )

        for name, field in self.fields.items():
            css = (
                "form-select"
                if isinstance(field, (forms.ChoiceField, forms.ModelChoiceField))
                else "form-control"
            )
            field.widget.attrs.setdefault("class", css)
        self.fields["q"].widget.attrs.setdefault(
            "placeholder", "Search by name, mobile, email, college or course"
        )
        self.fields["admission_year"].widget.attrs.setdefault(
            "placeholder", "e.g. 2026"
        )
