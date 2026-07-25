from django.contrib import admin

from accounts.models import User
from core.admin_mixins import CollegeScopedAdminMixin
from core.admin_site import campora_admin_site

from .models import AuditLog


@admin.register(AuditLog, site=campora_admin_site)
class AuditLogAdmin(CollegeScopedAdminMixin, admin.ModelAdmin):
    """Phase 3C, Feature 4/5: Campora Administration Panel integration
    for Audit Logs -- explicitly NOT built in Phase 3B ("Do NOT implement
    Admin Integration"), now the whole point of this phase.

    Feature 4's access matrix is enforced by two independent layers,
    matching the pattern already established for every other model here:
      - Platform Admin / College Admin only, and College Admin scoped to
        their own college only -- via CollegeScopedAdminMixin, whose
        default `college_lookup = "college"` needs no override since
        AuditLog already has a real `college` FK (added in Phase 3B
        specifically for efficient scoped querying).
      - College Staff and Students never reach this at all --
        `campora_admin_site.has_permission()` itself only allows
        Platform Admin / College Admin logins, so "Staff: No Audit Log" /
        "Students: No Audit Log" (Feature 4) is structurally guaranteed
        before CollegeScopedAdminMixin's own checks ever run.

    Immutable in the admin too (Feature 5, unchanged from Phase 3B):
    no add, no change, no delete -- consistent with the model's own
    save()/delete() overrides and its ImmutableQuerySet, which would
    reject any attempt that somehow got past these permission checks
    anyway (defense in depth).
    """

    list_display = ("id", "action", "action_category", "severity", "actor", "college", "target_model", "created_at")
    list_filter = (
        "severity", "action_category", "action", "college", "target_model", "actor_role",
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "action", "action_category", "object_display_name", "target_model",
        "actor__username", "actor__first_name", "actor__last_name",
    )
    # NOTE: deliberately no `date_hierarchy` here -- see the identical,
    # more detailed note in timeline.admin.TimelineEntryAdmin. MySQL's
    # CONVERT_TZ() requirement for the TruncMonth/TruncDay annotations
    # date_hierarchy uses raises a hard ValueError on any MySQL server
    # without timezone tables loaded -- confirmed by a real crash report
    # against the equivalent, longer-standing
    # core.admin_site.ReadOnlyLogEntryAdmin. DateFieldListFilter above
    # gives Feature 1's "search by Date" without that requirement.
    ordering = ("-created_at",)
    list_select_related = ("actor", "college")  # Feature 6
    list_per_page = 50  # Feature 3/6
    show_full_result_count = False  # Feature 6: avoid a slow COUNT(*) on a large table
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_list_filter(self, request):
        """Same reasoning as timeline.admin.TimelineEntryAdmin -- don't
        show a College Admin every other college's name in a dropdown
        their queryset can never actually return rows for."""
        if request.user.role == User.Role.SUPER_ADMIN:
            return self.list_filter
        return tuple(f for f in self.list_filter if f != "college")
