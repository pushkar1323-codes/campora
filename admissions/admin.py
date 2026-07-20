"""Django admin configuration for the admissions app (Campora).

Registered on core.admin_site.campora_admin_site (the custom Campora
Administration Panel), not the default admin.site.

The admin deliberately operates on `Enquiry.all_objects` (not the default
`Enquiry.objects`) so that staff/administrators using the Django admin can
see soft-deleted records too — the admin is an internal tool, distinct from
the staff-facing Recycle Bin UI (Phase 8). This predates the Admin Panel
Upgrade and is preserved unchanged; college-ownership scoping is layered
on top of it below rather than replacing it.
"""
from django.contrib import admin

from accounts.decorators import get_staff_college
from accounts.models import User
from core.admin_mixins import CollegeScopedAdminMixin
from core.admin_site import campora_admin_site

from .models import CorrectionRequest, Enquiry


@admin.register(Enquiry, site=campora_admin_site)
class EnquiryAdmin(CollegeScopedAdminMixin, admin.ModelAdmin):
    list_display = (
        "full_name",
        "email",
        "mobile",
        "college",
        "course",
        "status",
        "admission_year",
        "is_deleted",
        "created_at",
    )
    list_filter = ("status", "gender", "admission_year", "college", "course", "is_deleted")
    search_fields = ("full_name", "email", "mobile", "father_name", "college__name", "course__course_name")
    ordering = ("-created_at",)
    readonly_fields = ("college", "created_at", "updated_at")
    list_select_related = ("college", "course")
    autocomplete_fields = ("course", "submitted_by")
    actions = ["mark_as_deleted", "restore_selected"]

    fieldsets = (
        ("Student Details", {
            "fields": ("full_name", "father_name", "email", "mobile", "address", "dob", "gender")
        }),
        ("Academic Details", {
            "fields": ("qualification", "percentage", "course", "college", "admission_year")
        }),
        ("Account Link", {
            "fields": ("submitted_by",),
            "description": "Set automatically once student accounts exist (future phase); optional for now.",
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
        # Deliberately NOT calling super().get_queryset() (which would
        # resolve to CollegeScopedAdminMixin -> admin.ModelAdmin and use
        # Enquiry.objects, the soft-delete-filtered default manager) —
        # this must stay on Enquiry.all_objects to preserve the existing,
        # documented "admin sees deleted rows too" behavior above.
        qs = self.model.all_objects.get_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        if request.user.role == User.Role.SUPER_ADMIN:
            return qs
        college = get_staff_college(request.user)
        return qs.filter(college_id=college.id) if college is not None else qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # A College Admin must never see other colleges' courses in the
        # "Course" dropdown — course.college derives Enquiry.college on
        # save (see Enquiry.save()), so this is what actually prevents a
        # College Admin from routing an enquiry to another college.
        if db_field.name == "course" and request.user.role != User.Role.SUPER_ADMIN:
            college = get_staff_college(request.user)
            from courses.models import Course
            kwargs["queryset"] = (
                Course.objects.filter(college=college) if college else Course.objects.none()
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.action(description="Soft delete selected enquiries")
    def mark_as_deleted(self, request, queryset):
        updated = queryset.update(is_deleted=True)
        self.message_user(request, f"{updated} enquiry(ies) marked as deleted.")

    @admin.action(description="Restore selected enquiries")
    def restore_selected(self, request, queryset):
        updated = queryset.update(is_deleted=False)
        self.message_user(request, f"{updated} enquiry(ies) restored.")


@admin.register(CorrectionRequest, site=campora_admin_site)
class CorrectionRequestAdmin(CollegeScopedAdminMixin, admin.ModelAdmin):
    """Phase 1: read/audit view of Correction Requests in the Campora
    Admin Panel. The actual create/resolve workflow happens through the
    staff-facing enquiry detail page (dashboard app) — this registration
    exists for administrators to review the full history, scoped to their
    own college the same way every other college-owned model here is.
    """

    college_lookup = "enquiry__college"
    list_display = ("enquiry", "reason", "status", "requested_by", "created_at", "resolved_at")
    list_filter = ("status", "enquiry__college")
    search_fields = ("reason", "message", "enquiry__full_name", "enquiry__email")
    autocomplete_fields = ("enquiry",)
    readonly_fields = ("requested_by", "responded_at", "resolved_by", "resolved_at", "created_at", "updated_at")
    ordering = ("-created_at",)
