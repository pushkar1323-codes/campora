"""
Forms for the dashboard app.

EnquiryFilterForm (Phase 6): search/filter/sort controls for the enquiry
listing, bound to request.GET.

EnquiryUpdateForm (Phase 7): lets staff edit an existing Enquiry,
including reassigning its College/Course.
"""
from django import forms

from admissions.models import Enquiry
from courses.models import College, Course

_TEXT_INPUT = "form-control"
_SELECT = "form-select"


class CourseSelectWithCollegeData(forms.Select):
    """A plain <select>, except each <option> also carries
    data-college="<college id>" — used by enquiry_edit.html's small
    progressive-enhancement script to filter the Course dropdown when the
    College dropdown changes. Purely a UX convenience: the actual
    college/course pairing is always re-validated server-side in
    EnquiryUpdateForm.clean() regardless of what this script does.
    """

    def __init__(self, *args, course_college_map=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.course_college_map = course_college_map or {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        college_id = self.course_college_map.get(str(value)) if value not in (None, "") else None
        if college_id:
            option["attrs"]["data-college"] = str(college_id)
        return option


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
    """Phase 6: search/filter/sort controls for the enquiry listing.

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


class EnquiryUpdateForm(forms.ModelForm):
    """Phase 7: edit an existing Enquiry, including reassigning its
    College/Course.

    Architecture note: `Enquiry.college` is `editable=False` on the model
    and `Enquiry.save()` always re-derives it from `course.college` (see
    admissions/models.py) — this invariant ("college can never drift from
    its course") predates Phase 7 and is left untouched here. The
    `college` field on *this form* is therefore not a real model field:
    it exists purely so staff can pick a college first and get a Course
    dropdown scoped to that college, and so `clean()` can validate the
    pairing (MASTER_RULES.docx section 6 / DATABASE_DESIGN.docx section 7:
    "the selected Course must belong to the selected College"). Once the
    form validates, saving it only ever touches `course` — the actual
    `college` on the instance is still set by `Enquiry.save()` itself, the
    same way it always has been.
    """

    college = forms.ModelChoiceField(
        queryset=College.objects.none(), required=True, label="College"
    )

    class Meta:
        model = Enquiry
        fields = [
            "course",
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
            "status",
            "staff_notes",
        ]
        widgets = {
            "course": forms.Select(attrs={"class": _SELECT}),
            "full_name": forms.TextInput(attrs={"class": _TEXT_INPUT}),
            "father_name": forms.TextInput(attrs={"class": _TEXT_INPUT}),
            "email": forms.EmailInput(attrs={"class": _TEXT_INPUT}),
            "mobile": forms.TextInput(attrs={"class": _TEXT_INPUT}),
            "address": forms.Textarea(attrs={"class": _TEXT_INPUT, "rows": 2}),
            "dob": forms.DateInput(attrs={"class": _TEXT_INPUT, "type": "date"}),
            "gender": forms.Select(attrs={"class": _SELECT}),
            "qualification": forms.TextInput(attrs={"class": _TEXT_INPUT}),
            "percentage": forms.NumberInput(
                attrs={"class": _TEXT_INPUT, "step": "0.01", "min": "0", "max": "100"}
            ),
            "admission_year": forms.NumberInput(attrs={"class": _TEXT_INPUT}),
            "status": forms.Select(attrs={"class": _SELECT}),
            "staff_notes": forms.Textarea(attrs={"class": _TEXT_INPUT, "rows": 3}),
        }

    # Phase 1, Feature 1/3/7: personal-information fields, as opposed to
    # admission-workflow fields. Never editable by College Admin/College
    # Staff — see `can_edit_personal` below and
    # admissions/services.py::can_staff_edit_personal_fields.
    PERSONAL_FIELDS = ["full_name", "father_name", "email", "mobile", "address", "dob", "gender"]

    def __init__(self, *args, staff_college=None, can_edit_personal=False, **kwargs):
        """`staff_college`: pass the College of a logged-in College
        Admin/Staff user to lock this form to "college ownership" rules,
        the same rule EnquiryFilterForm follows:

        - The `college` field's queryset is restricted to just that one
          college and the field is `disabled` — Django disabled fields
          always use their `initial` value and silently ignore whatever
          was actually submitted, so even a hand-crafted POST body can't
          move the enquiry to another college.
        - The `course` field's choices are restricted to that college's
          courses only, so there is no course to pick that would move the
          enquiry elsewhere even before `clean()` runs.

        With `staff_college=None` (Platform Admin), both fields cover
        every college/course on the platform, and `college` starts
        pre-selected to the instance's current college (for the initial
        GET) so the Course dropdown's grouping makes sense at a glance.

        `can_edit_personal` (Phase 1): pass
        `admissions.services.can_staff_edit_personal_fields(request.user)`
        from the view. When False (College Admin, College Staff), every
        field in PERSONAL_FIELDS is removed from the form entirely — not
        just disabled — so there is no input to render, submit, or tamper
        with for student personal information. Staff use the Request
        Correction workflow instead (see dashboard/views.py::request_correction).
        Only a Platform Admin (the only role with this permission, per
        Feature 7) sees and can submit these fields — also the only way to
        correct an anonymous/guest enquiry's personal data, since a guest
        has no account for a correction request to reach.
        """
        super().__init__(*args, **kwargs)
        if not can_edit_personal:
            for field_name in self.PERSONAL_FIELDS:
                del self.fields[field_name]
        if staff_college is not None:
            self.fields["college"].queryset = College.objects.filter(
                pk=staff_college.pk
            )
            self.fields["college"].initial = staff_college
            self.fields["college"].disabled = True
            self.fields["course"].queryset = Course.objects.filter(
                college=staff_college
            ).order_by("course_name")
        else:
            self.fields["college"].queryset = College.objects.order_by("name")
            course_qs = Course.objects.select_related("college").order_by(
                "college__name", "course_name"
            )
            course_map = {str(c.pk): str(c.college_id) for c in course_qs}
            # Widget must be swapped in *before* the queryset is assigned:
            # ModelChoiceField's queryset setter is what actually populates
            # widget.choices (`self.widget.choices = self.choices`) — doing
            # it in this order means the new widget ends up with the right
            # choices instead of an empty dropdown.
            self.fields["course"].widget = CourseSelectWithCollegeData(
                attrs={"class": _SELECT}, course_college_map=course_map
            )
            self.fields["course"].queryset = course_qs
            self.fields["course"].label_from_instance = (
                lambda course: f"{course.course_name} ({course.college.name})"
            )
            if self.instance and self.instance.pk:
                self.fields["college"].initial = self.instance.college_id

        self.fields["college"].widget.attrs.setdefault("class", _SELECT)

    def clean(self):
        cleaned = super().clean()
        college = cleaned.get("college")
        course = cleaned.get("course")
        if college and course and course.college_id != college.id:
            self.add_error(
                "course",
                "This course does not belong to the selected college. "
                "Choose a course offered by that college.",
            )
        return cleaned
