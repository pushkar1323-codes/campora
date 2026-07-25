from django.contrib import admin

from accounts.models import User
from core.admin_mixins import CollegeScopedAdminMixin
from core.admin_site import campora_admin_site

from .models import TimelineEntry


@admin.register(TimelineEntry, site=campora_admin_site)
class TimelineEntryAdmin(CollegeScopedAdminMixin, admin.ModelAdmin):
    """Phase 3C, Feature 4/5: college-scoped Admin Panel integration.

    Upgraded from Phase 3A's Platform-Admin-only registration now that
    TimelineEntry has a real `college` FK (added this phase specifically
    for this) -- `CollegeScopedAdminMixin`'s default `college_lookup =
    "college"` needs no override. A Platform Admin sees every entry; a
    College Admin sees only entries explicitly tagged with their own
    college at creation time (see the `college` field's own docstring
    for why that tagging is optional and caller-supplied, not resolved
    generically through `content_object`). College Staff and Students
    never reach this at all -- `campora_admin_site.has_permission()`
    itself only allows Platform Admin / College Admin logins.

    Still read-only -- entries are immutable automatic history, never
    created or edited through the admin, regardless of role.
    """

    list_display = ("id", "category", "event_type", "title", "actor", "college", "created_at")
    list_filter = ("category", "event_type", "college", "content_type", ("created_at", admin.DateFieldListFilter))
    search_fields = (
        "title", "description", "event_type",
        "actor__username", "actor__first_name", "actor__last_name",
    )
    # NOTE: deliberately no `date_hierarchy` here -- it annotates with
    # TruncMonth/TruncDay, which MySQL executes via CONVERT_TZ() under
    # USE_TZ=True, and raises a hard ValueError if the server's timezone
    # tables aren't loaded (the out-of-the-box state on most Windows
    # MySQL installs -- confirmed by a real crash report on the
    # equivalent core.admin_site.ReadOnlyLogEntryAdmin, which used to set
    # it). The DateFieldListFilter above gives the same "search/filter by
    # Date" capability (Feature 1/2) via plain range lookups instead,
    # which need no server-side timezone conversion at all.
    ordering = ("-created_at",)
    list_select_related = ("actor", "college", "content_type")  # Feature 6
    list_per_page = 50  # Feature 3/6: pagination, large-dataset friendly
    show_full_result_count = False  # Feature 6: avoid a slow COUNT(*) on a large table
    readonly_fields = [f.name for f in TimelineEntry._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_list_filter(self, request):
        """Feature 4: a College Admin's queryset is already scoped to
        their own college (via CollegeScopedAdminMixin.get_queryset) --
        showing the "college" filter to them would only ever offer a
        choice of one, while listing every *other* college's name in the
        dropdown (Django's admin FK filter queries the related model
        directly, not the already-scoped queryset). Not a security
        issue (the underlying rows stay properly scoped either way), but
        needless information disclosure this phase's own "College
        Isolation" theme argues for removing.
        """
        if request.user.role == User.Role.SUPER_ADMIN:
            return self.list_filter
        return tuple(f for f in self.list_filter if f != "college")
