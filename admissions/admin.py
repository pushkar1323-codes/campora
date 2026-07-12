"""Django admin configuration for the admissions app (Campora).

The admin deliberately operates on `Enquiry.all_objects` (not the default
`Enquiry.objects`) so that staff/administrators using the Django admin can
see soft-deleted records too — the admin is an internal tool, distinct from
the staff-facing Recycle Bin UI that will be built in Phase 8.
"""
from django.contrib import admin

from .models import Enquiry


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "email",
        "mobile",
        "course",
        "status",
        "admission_year",
        "is_deleted",
        "created_at",
    )
    list_filter = ("status", "gender", "admission_year", "course", "is_deleted")
    search_fields = ("full_name", "email", "mobile", "father_name")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("course",)
    actions = ["mark_as_deleted", "restore_selected"]

    fieldsets = (
        ("Student Details", {
            "fields": ("full_name", "father_name", "email", "mobile", "address", "dob", "gender")
        }),
        ("Academic Details", {
            "fields": ("qualification", "percentage", "course", "admission_year")
        }),
        ("Workflow", {
            "fields": ("status", "staff_notes", "is_deleted")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def get_queryset(self, request):
        # Use all_objects (not the soft-delete-filtered default manager) so
        # staff can see and manage deleted enquiries directly in the admin.
        qs = self.model.all_objects.get_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    @admin.action(description="Soft delete selected enquiries")
    def mark_as_deleted(self, request, queryset):
        updated = queryset.update(is_deleted=True)
        self.message_user(request, f"{updated} enquiry(ies) marked as deleted.")

    @admin.action(description="Restore selected enquiries")
    def restore_selected(self, request, queryset):
        updated = queryset.update(is_deleted=False)
        self.message_user(request, f"{updated} enquiry(ies) restored.")
