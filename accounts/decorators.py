"""
Role-based authorization helpers for Campora.

Centralizes "who is allowed to see this view" logic in one place instead
of repeating role checks in every view — reduces duplication and makes the
authorization rules easy to audit.
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*allowed_roles):
    """View decorator: requires login AND that request.user.role is one of
    `allowed_roles`. Unauthenticated users are redirected to login (via
    Django's login_required); authenticated users with the wrong role get
    a 403.

    Usage:
        @role_required(User.Role.SUPER_ADMIN)
        def platform_dashboard(request): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if request.user.role not in allowed_roles:
                raise PermissionDenied(
                    "You do not have permission to access this page."
                )
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def get_staff_college(user):
    """Return the College a College Admin/Staff user belongs to, or None.

    Centralizing this lookup (rather than accessing user.staff_profile.college
    directly everywhere) means every college-scoped view enforces "college
    ownership" the same way, and a user who somehow lacks a StaffProfile
    fails safely (None) instead of raising.
    """
    return getattr(getattr(user, "staff_profile", None), "college", None)
