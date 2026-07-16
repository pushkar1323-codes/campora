"""Django admin configuration for the accounts app (Campora).

Registers the custom User model (with role-based fields) and the
StudentProfile / StaffProfile role-extension models.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import StaffProfile, StudentProfile, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Extends Django's built-in UserAdmin with the `role` field."""

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


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "date_of_birth", "created_at")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name", "phone")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user",)


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "college", "designation", "phone", "created_at")
    list_filter = ("college",)
    search_fields = ("user__username", "user__email", "college__name", "designation")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("user", "college")
    autocomplete_fields = ("user", "college")
