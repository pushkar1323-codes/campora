"""
Forms for the accounts app.

Two distinct creation paths, matching the platform's role hierarchy:
- Students self-register (StudentSignUpForm).
- College Admin / College Staff accounts are *provisioned*, not
  self-registered: a College Admin creates College Staff for their own
  college; a Platform Admin creates College Admins for a college
  (StaffCreationForm). The college is always passed in by the view from
  the requesting user's own context — never a form field — so a College
  Admin cannot provision staff for a college they don't own.

No email verification / OTP / social login: out of scope for this phase
per the platform vision document.
"""
from django.contrib.auth.forms import UserCreationForm
from django.forms import CharField, DateField, ModelForm, Textarea, TextInput

from .models import StaffProfile, StudentProfile, User

_TEXT_WIDGET = TextInput(attrs={"class": "form-control"})


class StudentSignUpForm(UserCreationForm):
    """Self-service student registration."""

    first_name = CharField(max_length=150, widget=_TEXT_WIDGET)
    last_name = CharField(max_length=150, widget=_TEXT_WIDGET)
    email = CharField(widget=TextInput(attrs={"class": "form-control", "type": "email"}))
    phone = CharField(max_length=15, required=False, widget=_TEXT_WIDGET)
    date_of_birth = DateField(
        required=False, widget=TextInput(attrs={"class": "form-control", "type": "date"})
    )
    address = CharField(required=False, widget=Textarea(attrs={"class": "form-control", "rows": 2}))

    class Meta:
        model = User
        fields = (
            "username", "first_name", "last_name", "email",
            "password1", "password2", "phone", "date_of_birth", "address",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("username", "password1", "password2"):
            self.fields[field_name].widget.attrs.update({"class": "form-control"})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.STUDENT
        if commit:
            user.save()
            StudentProfile.objects.create(
                user=user,
                phone=self.cleaned_data.get("phone", ""),
                date_of_birth=self.cleaned_data.get("date_of_birth"),
                address=self.cleaned_data.get("address", ""),
            )
        return user


class StaffCreationForm(UserCreationForm):
    """Creates a College Admin or College Staff user + their StaffProfile.

    `role` and `college` are set by the calling view based on who is
    submitting the form (see accounts/decorators.py::get_staff_college and
    dashboard/views.py), not exposed as user-editable form fields — this is
    what enforces "college ownership": a College Admin can only ever
    provision staff for their own college.
    """

    designation = CharField(max_length=100, required=False, widget=_TEXT_WIDGET)
    phone = CharField(max_length=15, required=False, widget=_TEXT_WIDGET)

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "password1", "password2")
        widgets = {
            "username": _TEXT_WIDGET,
            "first_name": _TEXT_WIDGET,
            "last_name": _TEXT_WIDGET,
            "email": TextInput(attrs={"class": "form-control", "type": "email"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("password1", "password2"):
            self.fields[field_name].widget.attrs.update({"class": "form-control"})

    def save(self, role, college, commit=True):
        user = super().save(commit=False)
        user.role = role
        # is_staff=True only for COLLEGE_ADMIN — required to log into the
        # Campora Administration Panel at all (Django's own
        # AdminAuthenticationForm hard-requires is_staff independently of
        # our custom CamporaAdminSite.has_permission() check; see
        # core/admin_site.py). COLLEGE_STAFF intentionally gets no admin
        # access, per the Admin Panel Upgrade spec — they keep using the
        # college-scoped dashboard only. What a College Admin can actually
        # see/do once inside the admin is then scoped to `college` by
        # core/admin_mixins.py, not by this flag — this only gets them
        # through the door.
        user.is_staff = role == User.Role.COLLEGE_ADMIN
        if commit:
            user.save()
            StaffProfile.objects.create(
                user=user,
                college=college,
                designation=self.cleaned_data.get("designation", ""),
                phone=self.cleaned_data.get("phone", ""),
            )
        return user
