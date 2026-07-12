"""
Forms for the core (public website) app.

ContactForm is intentionally a plain `forms.Form`, not a `ModelForm`.
DATABASE_DESIGN.docx does not define a table for general contact messages
(only Enquiry and Course), so this phase does not invent one. The form
validates input and, on success, the view surfaces a confirmation message
to the visitor. Persisting contact messages to the database (and/or
emailing them to staff) can be added in a later phase if that becomes a
requirement — see the note in views.py.
"""
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.forms import CharField, EmailField, Form, Textarea, TextInput

phone_validator = RegexValidator(
    regex=r"^\+?\d{7,15}$",
    message="Enter a valid phone number (7-15 digits, optional leading +).",
)


class ContactForm(Form):
    """General-purpose 'Contact Us' enquiry — distinct from the Admission
    Enquiry form built in Phase 4, which captures course-specific admission
    details and is backed by the Enquiry model.
    """

    full_name = CharField(
        label="Full Name",
        max_length=100,
        widget=TextInput(attrs={"class": "form-control", "placeholder": "Your full name"}),
    )
    email = EmailField(
        label="Email Address",
        widget=TextInput(attrs={"class": "form-control", "placeholder": "you@example.com", "type": "email"}),
    )
    phone = CharField(
        label="Phone Number",
        max_length=15,
        required=False,
        validators=[phone_validator],
        widget=TextInput(attrs={"class": "form-control", "placeholder": "Optional"}),
    )
    subject = CharField(
        label="Subject",
        max_length=150,
        widget=TextInput(attrs={"class": "form-control", "placeholder": "How can we help?"}),
    )
    message = CharField(
        label="Message",
        widget=Textarea(attrs={"class": "form-control", "rows": 5, "placeholder": "Write your message here..."}),
        min_length=10,
        max_length=2000,
    )

    def clean_full_name(self):
        # Guard against pure-whitespace input that CharField's default
        # trimming wouldn't otherwise catch as clearly.
        value = self.cleaned_data["full_name"].strip()
        if not value:
            raise ValidationError("Full name cannot be empty.")
        return value
