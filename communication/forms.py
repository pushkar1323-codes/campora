from django import forms

from .models import Message


class MessageForm(forms.ModelForm):
    """Reusable reply form — used identically by admissions (student
    self-service) and dashboard (staff) views. Only ever produces a
    Type.USER message; message_type/sender/thread are set by
    CommunicationService.post_message, never by this form.
    """

    class Meta:
        model = Message
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(attrs={
                "class": "form-control", "rows": 2, "placeholder": "Write a message...",
            }),
        }


class MessageEditForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
