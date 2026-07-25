"""
Campora Administration Panel — a custom django.contrib.admin AdminSite
replacing the default admin.site entirely (see config/urls.py).

Why a custom AdminSite instead of the default: `has_permission()` below
is the actual server-side gate deciding who can even reach the admin at
all, checked on *every* admin request via AdminSite.admin_view(). It
checks `request.user.role` directly rather than Django's is_staff/
permission-group system — the same authorization model the rest of this
app already uses (accounts.decorators.role_required). Per-model,
per-object scoping (a College Admin only ever seeing their own college's
data) is layered on top by core/admin_mixins.py, applied to each
ModelAdmin in accounts/admin.py, courses/admin.py, admissions/admin.py.

Login still requires `user.is_staff=True` — that check lives inside
Django's own AdminAuthenticationForm and can't be bypassed by overriding
AdminSite, so seed_data.py and StaffCreationForm.save() now set
`is_staff=True` for COLLEGE_ADMIN accounts (not COLLEGE_STAFF — they get
no admin access at all, per spec). is_staff only gets a user *in the
door*; has_permission() and the per-model mixins decide what they can
actually see and do once inside.
"""
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.urls import reverse
from django.utils import timezone

from accounts.decorators import get_staff_college
from accounts.models import User


class CamporaAdminSite(admin.AdminSite):
    site_header = "Campora Administration Panel"
    site_title = "Campora Admin"
    index_title = "Welcome to Campora Administration"

    def has_permission(self, request):
        """The real access gate for the whole panel — checked by Django
        admin on every single request, not just to decide what to show in
        a menu. Only Platform Admin and College Admin get in; College
        Staff and Student are turned away here regardless of is_staff.
        """
        user = request.user
        return (
            user.is_active
            and user.is_authenticated
            and user.role in (User.Role.SUPER_ADMIN, User.Role.COLLEGE_ADMIN)
        )

    def index(self, request, extra_context=None):
        """Campora Overview dashboard cards, injected above the standard
        app-list. Role-scoped: Platform Admin sees platform-wide totals;
        College Admin sees only their own college's numbers — the same
        split as dashboard/views.py::platform_dashboard vs.
        college_dashboard, just surfaced here too since this is now a
        second place a College Admin can land.
        """
        from admissions.models import Enquiry
        from courses.models import College, Course

        today_start = timezone.localdate()
        context = extra_context or {}

        if request.user.is_authenticated and request.user.role == User.Role.SUPER_ADMIN:
            context["campora_is_platform_scope"] = True
            context["campora_stats"] = {
                "scope_label": "Platform-wide",
                "total_colleges": College.objects.count(),
                "pending_colleges": College.objects.filter(status=College.Status.PENDING).count(),
                "total_courses": Course.objects.count(),
                "total_enquiries": Enquiry.objects.count(),
                "deleted_enquiries": Enquiry.all_objects.filter(is_deleted=True).count(),
                "pending_enquiries": Enquiry.objects.filter(status=Enquiry.Status.NEW).count(),
                "today_enquiries": Enquiry.objects.filter(created_at__date=today_start).count(),
                "total_staff": User.objects.filter(
                    role__in=(User.Role.COLLEGE_ADMIN, User.Role.COLLEGE_STAFF)
                ).count(),
                "total_students": User.objects.filter(role=User.Role.STUDENT).count(),
            }
            context["campora_recent_enquiries"] = (
                Enquiry.objects.select_related("college", "course").all()[:5]
            )
            context["campora_recent_activity"] = self.get_log_entries(request)[:8]
            context["campora_quick_links"] = [
                ("Colleges", reverse("admin:courses_college_changelist")),
                ("Courses", reverse("admin:courses_course_changelist")),
                ("Enquiries", reverse("admin:admissions_enquiry_changelist")),
                ("Users", reverse("admin:accounts_user_changelist")),
                ("Timeline", reverse("admin:timeline_timelineentry_changelist")),
                ("Audit Logs", reverse("admin:audit_auditlog_changelist")),
                ("Admin Action Log", reverse("admin:admin_logentry_changelist")),
            ]
        elif request.user.is_authenticated and request.user.role == User.Role.COLLEGE_ADMIN:
            college = get_staff_college(request.user)
            if college is not None:
                context["campora_stats"] = {
                    "scope_label": college.name,
                    "total_courses": college.courses.count(),
                    "active_courses": college.courses.filter(is_active=True).count(),
                    "total_enquiries": Enquiry.objects.filter(college=college).count(),
                    "deleted_enquiries": Enquiry.all_objects.filter(college=college, is_deleted=True).count(),
                    "pending_enquiries": Enquiry.objects.filter(
                        college=college, status=Enquiry.Status.NEW
                    ).count(),
                    "today_enquiries": Enquiry.objects.filter(
                        college=college, created_at__date=today_start
                    ).count(),
                    "total_staff": college.staff_members.count(),
                }
                context["campora_recent_enquiries"] = (
                    Enquiry.objects.filter(college=college).select_related("course")[:5]
                )
                context["campora_recent_activity"] = [
                    entry for entry in self.get_log_entries(request)[:30]
                    if entry.user_id == request.user.id
                ][:8]
                context["campora_quick_links"] = [
                    ("Courses", reverse("admin:courses_course_changelist")),
                    ("Enquiries", reverse("admin:admissions_enquiry_changelist")),
                    ("Staff", reverse("admin:accounts_staffprofile_changelist")),
                    ("Timeline", reverse("admin:timeline_timelineentry_changelist")),
                    ("Audit Logs", reverse("admin:audit_auditlog_changelist")),
                ]

        context["campora_debug_mode"] = settings.DEBUG
        return super().index(request, extra_context=context)


campora_admin_site = CamporaAdminSite(name="campora_admin")


class ReadOnlyLogEntryAdmin(admin.ModelAdmin):
    """Phase 11 (Admin Panel Upgrade): Django admin's own action log --
    who added/changed/deleted objects through this admin site. Distinct
    from, and narrower than, the business-level Audit Logging Engine
    (audit.AuditLog, Phase 3B/3C) — this only ever sees actions taken
    *inside the Django admin itself*; the business AuditLog also covers
    logins, correction requests, status changes, college
    approvals, and anything else that happens through the app's own
    views. Kept registered (relabeled "Admin Action Log" in the
    dashboard's quick links — see index() above) rather than removed,
    since it's real, distinct data that predates and still complements
    the newer engine, not a placeholder duplicating it.

    Read-only and Platform-Admin-only (see has_add/change/delete_permission
    below): an audit trail that could itself be edited or deleted
    wouldn't be much of an audit trail.

    NOTE: deliberately no `date_hierarchy` here. Django's `date_hierarchy`
    drill-down annotates with `TruncMonth`/`TruncDay`, which MySQL
    executes via `CONVERT_TZ()` whenever `USE_TZ=True` — and that raises
    a hard `ValueError` ("Database returned an invalid datetime value...")
    if the MySQL server's timezone tables haven't been loaded
    (`mysql_tzinfo_to_sql`), which is the out-of-the-box state on most
    Windows MySQL installs (there's no bundled equivalent of the
    `mysql_tzinfo_to_sql` step Linux packages typically run for you).
    `("action_time", admin.DateFieldListFilter)` below gives the same
    "search/filter by date" capability via simple `__gte`/`__lt` range
    lookups on the raw column, which MySQL can satisfy without any
    server-side timezone conversion at all.
    """

    list_display = ("action_time", "user", "content_type", "object_repr", "action_flag")
    list_filter = ("action_flag", "content_type", ("action_time", admin.DateFieldListFilter))
    search_fields = ("object_repr", "user__username")
    list_select_related = ("user", "content_type")
    ordering = ("-action_time",)

    def has_module_permission(self, request):
        return request.user.is_authenticated and request.user.role == User.Role.SUPER_ADMIN

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


campora_admin_site.register(LogEntry, ReadOnlyLogEntryAdmin)
