from django.contrib import admin

from core.admin_mixins import CamporaAdminAccessMixin
from core.admin_site import campora_admin_site

from .models import Message, MessageThread, ThreadParticipant


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ("sender", "sender_role", "message_type", "content", "is_read", "is_deleted", "created_at")
    readonly_fields = fields
    can_delete = False
    show_change_link = False


class ThreadParticipantInline(admin.TabularInline):
    model = ThreadParticipant
    extra = 0
    fields = ("user", "role_label", "is_active", "joined_at")
    readonly_fields = ("joined_at",)


@admin.register(MessageThread, site=campora_admin_site)
class MessageThreadAdmin(CamporaAdminAccessMixin, admin.ModelAdmin):
    """Platform-Admin-only (`platform_admin_only = True`, the same
    mechanism accounts.StudentProfile uses in accounts/admin.py): a
    thread can belong to ANY object type across ANY future module, so
    there is no single college-scoping FK path this app could reasonably
    assume — CollegeScopedAdminMixin needs a concrete `college` lookup,
    which a generic (content_type, object_id) relation doesn't have.
    """

    platform_admin_only = True
    list_display = ("id", "content_type", "object_id", "created_at", "updated_at")
    list_filter = ("content_type",)
    readonly_fields = ("content_type", "object_id", "created_at", "updated_at")
    inlines = [ThreadParticipantInline, MessageInline]

    def has_add_permission(self, request):
        # Threads are only ever created via CommunicationService, never
        # by hand in the admin.
        return False


@admin.register(Message, site=campora_admin_site)
class MessageAdmin(CamporaAdminAccessMixin, admin.ModelAdmin):
    """Read-only audit view, Platform-Admin-only for the same reason as
    MessageThreadAdmin above — a Message's college (if any) is only
    reachable by walking a generic relation this app doesn't assume the
    shape of.
    """

    platform_admin_only = True
    list_display = ("id", "thread", "sender", "message_type", "is_read", "is_deleted", "created_at")
    list_filter = ("message_type", "is_read", "is_deleted")
    search_fields = ("content",)
    readonly_fields = [f.name for f in Message._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
