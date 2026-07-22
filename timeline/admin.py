from django.contrib import admin

from core.admin_mixins import CamporaAdminAccessMixin
from core.admin_site import campora_admin_site

from .models import TimelineEntry


@admin.register(TimelineEntry, site=campora_admin_site)
class TimelineEntryAdmin(CamporaAdminAccessMixin, admin.ModelAdmin):
    """Platform-Admin-only, same reasoning as communication.MessageAdmin
    and staff_notes.StaffNoteAdmin -- an entry's owner can be any model
    type, so there's no single `college` FK path a CollegeScopedAdminMixin
    could assume. Read-only -- entries are immutable automatic history,
    never created or edited through the admin.
    """

    platform_admin_only = True
    list_display = ("id", "content_type", "object_id", "category", "event_type", "title", "actor", "created_at")
    list_filter = ("category", "event_type", "content_type")
    search_fields = ("title", "description")
    readonly_fields = [f.name for f in TimelineEntry._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
