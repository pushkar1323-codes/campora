from django.contrib import admin

from core.admin_site import campora_admin_site

from .models import Notification


@admin.register(Notification, site=campora_admin_site)
class NotificationAdmin(admin.ModelAdmin):
    """Platform-Admin-only — same precedent as
    communication.MessageThread/Message and accounts.StudentProfile:
    personal, cross-college data with no natural college-ownership scoping
    (a recipient's own college membership is a separate concern from which
    college the notification's *subject* belongs to, and Notification.college
    is optional/caller-supplied — see the model's own docstring). Read-only:
    notifications are always system-generated via NotificationService,
    never manually authored or edited through the admin, regardless of role.
    """

    list_display = ("id", "recipient", "notification_type", "title", "priority", "is_read", "created_at")
    list_filter = ("notification_type", "priority", "is_read", ("created_at", admin.DateFieldListFilter))
    search_fields = (
        "title", "body", "notification_type",
        "recipient__username", "recipient__first_name", "recipient__last_name",
    )
    ordering = ("-created_at",)
    list_select_related = ("recipient", "college", "content_type")
    list_per_page = 50
    show_full_result_count = False
    readonly_fields = [f.name for f in Notification._meta.fields]

    def _platform_admin(self, request):
        return getattr(request.user, "is_platform_admin", False)

    def has_module_permission(self, request):
        return self._platform_admin(request)

    def has_view_permission(self, request, obj=None):
        return self._platform_admin(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
