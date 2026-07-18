"""
Reusable Django-admin permission/scoping mixins for the Campora
Administration Panel (core/admin_site.py).

Why this exists: Campora's authorization model is `accounts.User.role`,
not Django's built-in permission/group system — none of our role-based
accounts have ever been granted model permissions or group memberships
(see accounts/decorators.py::role_required, which every non-admin view in
this project already uses the same way). Django's *default* ModelAdmin
permission checks (`has_view_permission` etc.) fall back to
`request.user.has_perm(...)`, which would deny everyone who isn't a
Django superuser. These mixins replace that with role-based checks,
consistent with the rest of the app, and layer college-ownership scoping
on top for the models that belong to a college.

Server-side enforcement, not menu-hiding: every mixin method here is a
real permission check called by Django admin itself on every request
(list view, change view, delete view, and — critically — the *object*
passed to has_change_permission/has_delete_permission) — not just logic
that decides whether to show a link. A College Admin who guesses another
college's object URL still gets denied by has_change_permission/
has_view_permission below, the same "never trust the URL" rule
accounts/decorators.py::get_staff_college enforces everywhere else in
this app.
"""
from accounts.decorators import get_staff_college
from accounts.models import User


class CamporaAdminAccessMixin:
    """Base mixin: role-gates every permission Django admin checks.

    `platform_admin_only = True` (set on the subclass) restricts a
    ModelAdmin to Platform Admin entirely — used for User, Group, and
    StudentProfile (see admin_site.py module docstrings on those specific
    registrations for why each is scoped that way).
    """

    platform_admin_only = False

    def _role_allowed(self, request):
        user = request.user
        if not user.is_authenticated:
            return False
        if user.role == User.Role.SUPER_ADMIN:
            return True
        if self.platform_admin_only:
            return False
        return user.role == User.Role.COLLEGE_ADMIN

    def has_module_permission(self, request):
        return self._role_allowed(request)

    def has_view_permission(self, request, obj=None):
        return self._role_allowed(request)

    def has_add_permission(self, request):
        return self._role_allowed(request)

    def has_change_permission(self, request, obj=None):
        return self._role_allowed(request)

    def has_delete_permission(self, request, obj=None):
        return self._role_allowed(request)


class CollegeScopedAdminMixin(CamporaAdminAccessMixin):
    """For ModelAdmins whose model has a direct `college` ForeignKey
    (College, Course, StaffProfile, Enquiry — every college-owned model in
    this project has one). Set `college_lookup` on the subclass only if a
    given model's FK field is named something other than "college".

    A Platform Admin gets every row, full CRUD. A College Admin gets only
    rows belonging to their own college (via get_staff_college), full CRUD
    on those, and a hard permission-denied on anything else — checked
    both in the queryset (so it never appears in a list or autocomplete)
    and again at the object level (so a guessed URL for another college's
    object still gets denied, not just hidden from a list).
    """

    college_lookup = "college"

    def _object_college_id(self, obj):
        """Resolve the College id for `obj` via `college_lookup`, which may
        be a direct FK ("college") or a lookup path ("staff_profile__college").
        """
        target = obj
        for step in self.college_lookup.split("__"):
            target = getattr(target, step, None)
            if target is None:
                return None
        return getattr(target, "id", target)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == User.Role.SUPER_ADMIN:
            return qs
        college = get_staff_college(request.user)
        if college is None:
            return qs.none()
        return qs.filter(**{f"{self.college_lookup}_id": college.id})

    def has_view_permission(self, request, obj=None):
        if not super().has_view_permission(request, obj):
            return False
        return self._object_in_scope(request, obj)

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
        return self._object_in_scope(request, obj)

    def has_delete_permission(self, request, obj=None):
        if not super().has_delete_permission(request, obj):
            return False
        return self._object_in_scope(request, obj)

    def _object_in_scope(self, request, obj):
        """True if `obj` is None (list/add view — queryset scoping handles
        the rest) or belongs to the requesting College Admin's college."""
        if obj is None or request.user.role == User.Role.SUPER_ADMIN:
            return True
        college = get_staff_college(request.user)
        if college is None:
            return False
        return self._object_college_id(obj) == college.id
