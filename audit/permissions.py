"""
Reusable, generic permission helper for Audit Logs (Feature 9).

Deliberately stricter than every other reusable module built so far:
Feature 9 names exactly two roles -- "Only Platform Admin and authorized
College Admins may access logs" -- College Staff is conspicuously absent
(unlike Timeline and Communication, which both include College Staff).
That's a real, intentional narrowing this phase, not an oversight.

"Authorized" College Admin means scoped to their own college -- the
same two-tier split as every other reusable module here: this function
answers "does this role get to see audit logs at all", and the calling
dashboard view supplies which college's logs via its own existing
`get_staff_college` (unchanged), then calls
`audit.services.AuditService.get_logs_for_college(college)`.
"""


def can_view_audit_logs(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_platform_admin", False):
        return True
    from accounts.models import User
    return getattr(user, "role", None) == User.Role.COLLEGE_ADMIN
