"""
Context processor adding a small "recent notifications" slice + unread
count to every template's context, so the navbar bell
(templates/partials/navbar.html) can render on every authenticated page
without every single view needing to pass it explicitly — the same reason
`django.contrib.auth.context_processors.auth` already exists for
`request.user` itself, and already registered in config/settings.py's
TEMPLATES.

Read-only, side-effect-free — does NOT mark anything read (that's an
explicit user action; see notifications/views.py).
"""
from .services import NotificationService


def notifications_context(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {
        "nav_unread_count": NotificationService.get_unread_count(user),
        "nav_recent_notifications": NotificationService.get_notifications(user)[:8],
    }
