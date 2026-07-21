"""
Reusable, generic permission helpers for Internal Staff Notes (Feature 4).

Unlike communication/permissions.py, this module's rules are role-based
rather than participant-based -- Staff Notes have a fixed, explicit role
matrix (Feature 4), not an evolving list of thread participants. Every
function here depends only on `accounts.User.role` (a shared, core
dependency every reusable app in this project already takes -- see
communication/permissions.py's own precedent), never on
admissions.Enquiry or any other domain model.

College-ownership scoping (Feature 10: "Staff members may only access
enquiries belonging to their own college") is NOT implemented here --
exactly like communication/permissions.py's documented two-tier split,
that stays in dashboard's existing `_staff_scope`/`get_staff_college`
logic (unchanged since Phase 1), which every view below calls BEFORE
ever reaching a note. These functions answer "what can this role do with
notes in general", not "does this user own this particular enquiry".
"""


def can_view_notes(user):
    """Feature 4: Student -- never. College Staff/Admin, Platform Admin
    -- yes (college-ownership scoping already happened in the calling
    view before this is ever checked; see module docstring).
    """
    if not getattr(user, "is_authenticated", False):
        return False
    return not _is_student(user)


def can_create_note(user):
    """Same rule as can_view_notes -- anyone who can see notes can add one."""
    return can_view_notes(user)


def can_edit_note(user, note):
    """Feature 4: College Staff may edit only their OWN notes. College
    Admin and Platform Admin have "full access" -- any note. Once
    soft-deleted, a note is never directly editable (must be restored
    first).
    """
    if not can_view_notes(user):
        return False
    if note.is_deleted:
        return False
    if _is_admin_or_platform(user):
        return True
    return note.author_id == user.id


def can_delete_note(user, note):
    """Feature 4: same boundary as can_edit_note -- Staff may soft-delete
    only their own notes; Admin/Platform Admin may soft-delete any."""
    if not can_view_notes(user):
        return False
    if note.is_deleted:
        return False
    if _is_admin_or_platform(user):
        return True
    return note.author_id == user.id


def can_restore_note(user, note):
    """Feature 3/4: "Restore Note (Administrator only)" -- explicitly
    NOT available to plain College Staff, even for their own note. Only
    College Admin and Platform Admin.
    """
    if not note.is_deleted:
        return False
    return _is_admin_or_platform(user)


def _is_student(user):
    from accounts.models import User
    return getattr(user, "role", None) == User.Role.STUDENT


def _is_admin_or_platform(user):
    from accounts.models import User
    if getattr(user, "is_platform_admin", False):
        return True
    return getattr(user, "role", None) == User.Role.COLLEGE_ADMIN
