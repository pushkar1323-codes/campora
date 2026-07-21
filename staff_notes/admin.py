from django.contrib import admin

from core.admin_mixins import CamporaAdminAccessMixin
from core.admin_site import campora_admin_site

from .models import StaffNote


@admin.register(StaffNote, site=campora_admin_site)
class StaffNoteAdmin(CamporaAdminAccessMixin, admin.ModelAdmin):
    """Platform-Admin-only, same reasoning as communication.MessageAdmin
    -- a note's owner can be any model type, so there's no single
    `college` FK path a CollegeScopedAdminMixin could assume. Read-only
    audit view; the real create/edit/delete/restore workflow happens
    through the staff-facing enquiry detail page (dashboard app).
    """

    platform_admin_only = True
    list_display = ("id", "content_type", "object_id", "author", "is_deleted", "created_at")
    list_filter = ("content_type", "is_deleted")
    search_fields = ("content",)
    readonly_fields = [f.name for f in StaffNote._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
