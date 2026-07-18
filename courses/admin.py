"""Django admin configuration for the courses app (Campora): College and Course.

Registered on core.admin_site.campora_admin_site (the custom Campora
Administration Panel), not the default admin.site — see that module's
docstring for why. Both ModelAdmins below are role/college-scoped via
core/admin_mixins.py rather than Django's built-in permission system,
consistent with the rest of this app's authorization model.
"""
from django.contrib import admin

from accounts.decorators import get_staff_college
from accounts.models import User
from core.admin_mixins import CamporaAdminAccessMixin, CollegeScopedAdminMixin
from core.admin_site import campora_admin_site

from .models import College, Course


@admin.register(College, site=campora_admin_site)
class CollegeAdmin(CamporaAdminAccessMixin, admin.ModelAdmin):
    """College is the scoping *root* — it doesn't have a `college` FK to
    filter by (it *is* the college), so it can't use
    CollegeScopedAdminMixin as-is; scoping here is by `pk` directly.

    A College Admin may view/edit their own college's profile (branding,
    contact info) but never add or delete a College, and never see any
    other college — the lifecycle (approve/reject/suspend, and by
    extension existence) stays owned by the public registration +
    Platform Admin approval workflow (dashboard app), not raw admin CRUD.
    Platform Admin: full, unrestricted CRUD, per spec.
    """

    list_display = ("name", "city", "state", "status", "active_course_count", "updated_at")
    list_filter = ("status", "state", "city")
    search_fields = ("name", "city", "state", "email")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    actions = ["approve_colleges", "reject_colleges", "suspend_colleges"]

    fieldsets = (
        (None, {"fields": ("name", "slug", "status")}),
        ("Branding", {"fields": ("logo", "cover_image", "short_description", "description")}),
        ("Location & Contact", {"fields": ("address", "city", "state", "phone", "email", "website")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Active Courses")
    def active_course_count(self, obj):
        return obj.active_course_count

    @admin.action(description="Approve selected colleges")
    def approve_colleges(self, request, queryset):
        updated = queryset.update(status=College.Status.APPROVED)
        self.message_user(request, f"{updated} college(s) approved.")

    @admin.action(description="Reject selected colleges")
    def reject_colleges(self, request, queryset):
        updated = queryset.update(status=College.Status.REJECTED)
        self.message_user(request, f"{updated} college(s) rejected.")

    @admin.action(description="Suspend selected colleges")
    def suspend_colleges(self, request, queryset):
        updated = queryset.update(status=College.Status.SUSPENDED)
        self.message_user(request, f"{updated} college(s) suspended.")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == User.Role.SUPER_ADMIN:
            return qs
        college = get_staff_college(request.user)
        return qs.filter(pk=college.id) if college is not None else qs.none()

    def _is_own_college(self, request, obj):
        if obj is None or request.user.role == User.Role.SUPER_ADMIN:
            return True
        college = get_staff_college(request.user)
        return college is not None and obj.pk == college.id

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and self._is_own_college(request, obj)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and self._is_own_college(request, obj)

    def has_add_permission(self, request):
        # Colleges are created via the public registration + approval
        # workflow, not raw admin CRUD — Platform Admin only, even though
        # CamporaAdminAccessMixin would otherwise allow College Admin too.
        return request.user.is_authenticated and request.user.role == User.Role.SUPER_ADMIN

    def has_delete_permission(self, request, obj=None):
        return request.user.is_authenticated and request.user.role == User.Role.SUPER_ADMIN

    def get_actions(self, request):
        # Approve/reject/suspend actions change a college's own status —
        # keep these Platform-Admin-only regardless of who can view/edit
        # basic profile fields above.
        actions = super().get_actions(request)
        if request.user.role != User.Role.SUPER_ADMIN:
            for action in ("approve_colleges", "reject_colleges", "suspend_colleges"):
                actions.pop(action, None)
        return actions


@admin.register(Course, site=campora_admin_site)
class CourseAdmin(CollegeScopedAdminMixin, admin.ModelAdmin):
    """College Admin: full CRUD, scoped to their own college's courses
    only (CollegeScopedAdminMixin). Platform Admin: unrestricted."""

    list_display = ("course_name", "college", "duration", "is_active", "updated_at")
    list_filter = ("is_active", "college")
    search_fields = ("course_name", "eligibility", "college__name")
    list_select_related = ("college",)
    autocomplete_fields = ("college",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("college", "course_name", "duration", "eligibility", "description", "is_active")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # A College Admin must never see other colleges in the "College"
        # dropdown when adding/editing a Course — otherwise they could
        # move (or create) a course into a college they don't own, even
        # though get_queryset already hides those *rows* from the list.
        if db_field.name == "college" and request.user.role != User.Role.SUPER_ADMIN:
            college = get_staff_college(request.user)
            kwargs["queryset"] = College.objects.filter(pk=college.id) if college else College.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
