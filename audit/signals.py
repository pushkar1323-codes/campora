"""
Authentication audit logging via Django's own built-in auth signals --
NOT a custom event system (Feature/scope note: "Do NOT implement Event
Service" is honored here precisely because this uses a framework
mechanism that already exists, rather than introducing a new one).

Connecting here means every login/logout call site in the project
(CamporaLoginView, the auto-login after registration in
accounts/views.py::register_student, Django's own LogoutView used
as-is in accounts/urls.py, and any future login path) is covered
automatically, with zero code added at any of those call sites --
exactly Feature 7's "avoid duplicated logging logic".
"""
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import AuditLog
from .services import AuditService


@receiver(user_logged_in)
def log_user_logged_in(sender, request, user, **kwargs):
    AuditService.log(
        action="USER_LOGIN", category="Authentication", severity=AuditLog.Severity.INFO,
        event_source="Web", actor=user, object_display_name=user.get_username(),
        request=request,
    )


@receiver(user_logged_out)
def log_user_logged_out(sender, request, user, **kwargs):
    if user is None:
        # Django fires this even for an already-anonymous session in some
        # edge cases -- nothing meaningful to attribute the entry to.
        return
    AuditService.log(
        action="USER_LOGOUT", category="Authentication", severity=AuditLog.Severity.INFO,
        event_source="Web", actor=user, object_display_name=user.get_username(),
        request=request,
    )


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request=None, **kwargs):
    AuditService.log(
        action="USER_LOGIN_FAILED", category="Authentication", severity=AuditLog.Severity.WARNING,
        event_source="Web", object_display_name=credentials.get("username", "unknown"),
        request=request,
    )
