from django import forms

from .models import StaffNote


class StaffNoteForm(forms.ModelForm):
    """Used identically for both create and edit -- only ever produces
    the `content` field; author/content_type/object_id are set by
    StaffNoteService, never by this form.
    """

    class Meta:
        model = StaffNote
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(attrs={
                "class": "form-control", "rows": 2,
                "placeholder": "e.g. Waiting for original certificate, Student called today...",
            }),
        }
