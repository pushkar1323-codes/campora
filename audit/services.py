"""
AuditService — the single entry point every other app uses to write
Audit Log entries (Feature 7: "Avoid duplicated logging logic. Use
reusable services where appropriate.").

Two entry points, deliberately:
  - `log()` — the general form, for events with no natural target object
    (login/logout, a platform setting change, ...).
  - `log_for_object(obj, ...)` — a convenience wrapper that derives
    `target_model`/`object_id`/`object_display_name` from a plain model
    instance, so callers never hand-format those strings themselves
    (the equivalent discipline to encapsulating GenericForeignKey
    resolution in communication/timeline/staff_notes, applied to this
    app's disconnected-reference scheme instead — see models.py's module
    docstring for why AuditLog doesn't use a live GenericForeignKey).

IP address / user agent capture is centralized here too: a caller with
access to the current `request` just passes it through; this is the one
place that knows how to pull a real client IP out of
X-Forwarded-For/REMOTE_ADDR, so that logic never gets duplicated at each
call site either.
"""
from .models import AuditLog


class AuditService:
    """Stateless -- every method is a `@staticmethod`, same calling
    convention as TimelineService/CommunicationService/StaffNoteService.
    """

    @staticmethod
    def _client_ip(request):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    @staticmethod
    def log(
        action, category="", severity=AuditLog.Severity.INFO, event_source="Web",
        actor=None, actor_role="", college=None,
        target_model="", object_id="", object_display_name="",
        previous_values=None, new_values=None, snapshot_data=None,
        request=None, ip_address=None, user_agent="", metadata=None,
    ):
        """Feature 1/7: write one immutable audit record. `request`,
        when provided, supplies `ip_address`/`user_agent` automatically
        (explicit `ip_address`/`user_agent` arguments still win if both
        are given).
        """
        resolved_role = actor_role or (getattr(actor, "get_role_display", lambda: "")() if actor else "")
        resolved_ip = ip_address
        resolved_ua = user_agent
        if request is not None:
            resolved_ip = resolved_ip or AuditService._client_ip(request)
            resolved_ua = resolved_ua or request.META.get("HTTP_USER_AGENT", "")[:512]

        return AuditLog.objects.create(
            action=action, action_category=category, severity=severity, event_source=event_source,
            actor=actor, actor_role=resolved_role, college=college,
            target_model=target_model, object_id=str(object_id) if object_id not in ("", None) else "",
            object_display_name=object_display_name,
            previous_values=previous_values or {}, new_values=new_values or {}, snapshot_data=snapshot_data or {},
            ip_address=resolved_ip, user_agent=resolved_ua, metadata=metadata or {},
        )

    @staticmethod
    def log_for_object(
        obj, action, category="", severity=AuditLog.Severity.INFO, event_source="Web",
        actor=None, actor_role="", college=None, object_display_name="",
        previous_values=None, new_values=None, snapshot_data=None,
        request=None, ip_address=None, user_agent="", metadata=None,
    ):
        """Convenience wrapper: derives target_model/object_id (and a
        default object_display_name via `str(obj)`, override-able) from
        `obj`, then delegates to log() -- callers never construct the
        'app_label.model_name' string themselves.
        """
        return AuditService.log(
            action=action, category=category, severity=severity, event_source=event_source,
            actor=actor, actor_role=actor_role, college=college,
            target_model=f"{obj._meta.app_label}.{obj._meta.model_name}",
            object_id=obj.pk, object_display_name=object_display_name or str(obj),
            previous_values=previous_values, new_values=new_values, snapshot_data=snapshot_data,
            request=request, ip_address=ip_address, user_agent=user_agent, metadata=metadata,
        )

    @staticmethod
    def get_logs_for_object(obj):
        """Feature 8: pagination-ready (unsliced), indexed lookup by the
        same target_model/object_id convention log_for_object() writes.
        """
        return AuditLog.objects.filter(
            target_model=f"{obj._meta.app_label}.{obj._meta.model_name}", object_id=str(obj.pk)
        )

    @staticmethod
    def get_logs_for_college(college):
        """Feature 9: the college-scoped query a College Admin's view of
        the log needs. Pagination-ready (unsliced)."""
        return AuditLog.objects.filter(college=college)

    @staticmethod
    def get_all_logs():
        """Feature 9: Platform Admin's unrestricted view."""
        return AuditLog.objects.all()
