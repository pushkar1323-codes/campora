"""
Reusable, thread-level permission helpers (architectural improvement #4)
— views never inline permission logic; they call these instead.

Two-tier design, documented explicitly because it's the honest resolution
of a real tension in this phase's own brief: "don't couple this module to
Enquiry" versus "staff access must respect college-ownership scoping",
and college-ownership is inherently domain (admissions) knowledge this
module must never contain:

  1. GENERIC tier (this file): rules that need no domain knowledge at
     all — "is this user an active ThreadParticipant of this object's
     thread", "is this user the sender of this message", "is this user a
     Platform Admin (full access, per Feature 10)". These are exactly
     the checks a Hostel/Placements/... module could reuse unchanged.

  2. DOMAIN tier (the calling app): "is this student the owner of this
     enquiry", "is this staff member scoped to this enquiry's college".
     That logic already exists in admissions/dashboard (unchanged from
     Phase 1 — get_staff_college, _staff_scope, submitted_by=request.user)
     and stays exactly where it belongs. Every admissions/dashboard view
     that touches communication performs its existing domain-level
     authorization FIRST (fetching the Enquiry at all already proves
     it), then calls CommunicationService.add_participant(...) to make
     the now-authorized user an explicit thread participant, and only
     THEN (for the student-facing self-service flows) additionally
     checks the generic tier below as defense-in-depth. Staff-facing
     dashboard views rely on their existing domain-level scoping alone
     for thread access (see dashboard/views.py) — replicating a
     participant check there would be redundant, since staff only ever
     reach the thread through an already college-scoped Enquiry lookup.

can_edit_message / can_delete_message need no such split — "you sent it"
is fully generic and applies identically everywhere.
"""


def can_view_thread(user, obj):
    """Generic rule: a Platform Admin (Feature 10: "Full access"), or an
    active participant of `obj`'s thread, may view it. See module
    docstring for how staff-side domain authorization complements this.
    """
    from .services import CommunicationService

    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_platform_admin", False):
        return True
    return CommunicationService.is_participant(obj, user)


def can_send_message(user, obj):
    """Same rule as can_view_thread — you must already be a recognized
    participant (or Platform Admin) to reply. See module docstring."""
    return can_view_thread(user, obj)


def can_mark_thread_read(user, obj):
    """Same tier as can_view_thread — marking read is part of viewing."""
    return can_view_thread(user, obj)


def can_edit_message(user, message):
    """Feature 6, generic and identical for every caller: only the
    original sender may edit their own message, and only a genuine USER
    message (never SYSTEM/CORRECTION_REQUEST, and never once deleted).
    Platform Admin gets the same "Full access" override used everywhere
    else in this project (Feature 10).
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if message.is_deleted:
        return False
    if message.message_type != message.Type.USER:
        return False
    if getattr(user, "is_platform_admin", False):
        return True
    return message.sender_id == user.id


def can_delete_message(user, message):
    """Feature 7, generic: the sender may soft-delete their own message;
    Platform Admin may soft-delete any (Feature 10). System-generated
    messages are never user-deletable — they're the thread's own audit
    trail (e.g. a Correction Request being opened).
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if message.is_deleted:
        return False
    if message.message_type != message.Type.USER:
        return False
    if getattr(user, "is_platform_admin", False):
        return True
    return message.sender_id == user.id
