"""Django admin configuration for the accounts app (Campora).

Registers the custom User model (with role-based fields) and the
StudentProfile / StaffProfile role-extension models on
core.admin_site.campora_admin_site (the custom Campora Administration
Panel), not the default admin.site.

Scoping decisions (Admin Panel Upgrade spec):
- User, Group: Platform Admin only. The spec explicitly lists these among
  the things a College Admin "must never see" (Platform Settings,
  Superusers, Permissions, Groups, Global Users, System Configuration).
- StudentProfile: Platform Admin only. Flagged as a judgment call: unlike
  Course/StaffProfile/Enquiry, StudentProfile has no `college` FK in the
  current data model — a student isn't owned by any one college, they can
  enquire at several or none. There is no correct subset of "own
  students" to hand a College Admin, so rather than guess, this stays
  Platform-Admin-only until/unless the data model gains a real
  college-student relationship.
- StaffProfile: College-scoped via CollegeScopedAdminMixin — this is the
  literal "Own Staff" the spec asks for.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group

from core.admin_mixins import CamporaAdminAccessMixin, CollegeScopedAdminMixin
from core.admin_site import campora_admin_site

from .models import StaffProfile, StudentProfile, User


@admin.register(User, site=campora_admin_site)
class UserAdmin(CamporaAdminAccessMixin, DjangoUserAdmin):
    """Extends Django's built-in UserAdmin with the `role` field.
    Platform Admin only — see module docstring."""

    platform_admin_only = True

    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "is_staff",
        "is_active",
    )
    list_filter = DjangoUserAdmin.list_filter + ("role",)
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Campora Role", {"fields": ("role",)}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("Campora Role", {"fields": ("role",)}),
    )


@admin.register(Group, site=campora_admin_site)
class CamporaGroupAdmin(CamporaAdminAccessMixin, admin.ModelAdmin):
    """Django's built-in Group model, registered here (it is NOT
    auto-registered on a custom AdminSite the way it is on the default
    admin.site) so Platform Admin retains the "Groups" management the
    spec asks for. Platform Admin only, same reasoning as User above."""

    platform_admin_only = True
    search_fields = ("name",)


@admin.register(StudentProfile, site=campora_admin_site)
class StudentProfileAdmin(CamporaAdminAccessMixin, admin.ModelAdmin):
    """Platform Admin only — see module docstring for why this isn't
    college-scoped like StaffProfile."""

    platform_admin_only = True

    list_display = ("user", "phone", "date_of_birth", "created_at")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name", "phone")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user",)


@admin.register(StaffProfile, site=campora_admin_site)
class StaffProfileAdmin(CollegeScopedAdminMixin, admin.ModelAdmin):
    """College Admin: full CRUD, scoped to their own college's staff only
    (CollegeScopedAdminMixin). Platform Admin: unrestricted. This is the
    "Own Staff" management the spec asks for."""

    list_display = ("user", "college", "designation", "phone", "created_at")
    list_filter = ("college",)
    search_fields = ("user__username", "user__email", "college__name", "designation")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("user", "college")
    autocomplete_fields = ("user", "college")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # A College Admin must never be able to (re)assign a StaffProfile
        # to another college via this dropdown.
        if db_field.name == "college" and request.user.role != User.Role.SUPER_ADMIN:
            from accounts.decorators import get_staff_college
            from courses.models import College
            college = get_staff_college(request.user)
            kwargs["queryset"] = College.objects.filter(pk=college.id) if college else College.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
