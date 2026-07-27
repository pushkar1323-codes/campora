from django.contrib import admin

from core.admin_mixins import CamporaAdminAccessMixin
from core.admin_site import campora_admin_site

from .models import ContactMessage


@admin.register(ContactMessage, site=campora_admin_site)
class ContactMessageAdmin(CamporaAdminAccessMixin, admin.ModelAdmin):
    """Platform-Admin-only -- these are platform-level messages, not
    tied to any college, so CollegeScopedAdminMixin doesn't apply (same
    reasoning as accounts.StudentProfile). Read/triage only through the
    dashboard's dedicated Contact Messages page (dashboard:contact_messages)
    for the actual mark-read/resolve workflow; this registration exists
    so Platform Admin can also browse/search/filter here, consistent
    with every other model in this project.
    """

    platform_admin_only = True
    list_display = ("id", "subject", "full_name", "email", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("full_name", "email", "subject", "message")
    list_select_related = ("submitted_by", "read_by", "resolved_by")
    list_per_page = 50
    show_full_result_count = False
    readonly_fields = [f.name for f in ContactMessage._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
