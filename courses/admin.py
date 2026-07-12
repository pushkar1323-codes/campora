"""Django admin configuration for the courses app (Campora)."""
from django.contrib import admin

from .models import Course


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("course_name", "duration", "eligibility", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("course_name", "eligibility")
    ordering = ("course_name",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("course_name", "duration", "eligibility", "description", "is_active")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
