"""Django admin configuration for the courses app (Campora): College and Course."""
from django.contrib import admin

from .models import College, Course


@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
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


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
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
