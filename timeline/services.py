"""
TimelineService — the single entry point every other app uses to record
and read Timeline entries.

Same architectural rule as communication/services.py and
staff_notes/services.py: no other app, view, or form may import
ContentType, GenericForeignKey, or touch TimelineEntry.content_type/
object_id directly. Every caller passes a plain model instance (e.g. an
admissions.Enquiry) and this service resolves the generic relation
internally.

Unlike communication/staff_notes, there is no permissions module here.
Timeline is read-only, automatic history -- nobody creates, edits, or
deletes an entry through a permission-gated action; `log_event` is only
ever called from trusted application code (a view or service reacting to
a real state change), never directly by a user request. "Who may VIEW a
timeline" (Feature 5) is entirely a function of whether the calling view
already authorized access to the underlying object -- Student ownership
scoping in admissions, College scoping in dashboard, both unchanged from
earlier phases -- so there is no additional generic rule to encapsulate
the way Staff Notes' edit/delete/restore role matrix needed one.
"""
from django.contrib.contenttypes.models import ContentType

from .models import TimelineEntry


class TimelineService:
    """Stateless -- every method is a `@staticmethod`, same calling
    convention as CommunicationService/StaffNoteService.
    """

    @staticmethod
    def _content_type_for(obj):
        return ContentType.objects.get_for_model(type(obj))

    @staticmethod
    def log_event(obj, category, event_type, title, description="", actor=None, actor_role="", icon="", metadata=None):
        """Feature 3: record one automatic timeline entry against `obj`.
        Never called directly in response to a raw user request -- always
        from application code that has already decided a real event
        happened (enquiry submitted, status changed, a message sent, a
        correction requested/submitted/resolved, ...). See the call sites
        in admissions/services.py, admissions/views.py and
        dashboard/views.py for the concrete Feature 3 event list actually
        wired up this phase.
        """
        content_type = TimelineService._content_type_for(obj)
        resolved_role = actor_role or (getattr(actor, "get_role_display", lambda: "")() if actor else "")
        return TimelineEntry.objects.create(
            content_type=content_type, object_id=obj.pk,
            category=category, event_type=event_type, title=title, description=description,
            actor=actor, actor_role=resolved_role, icon=icon, metadata=metadata or {},
        )

    @staticmethod
    def get_timeline(obj):
        """Feature 4: newest-first (Model.Meta.ordering), select_related
        queryset -- deliberately not sliced (Feature 6: "Prepare for
        pagination", not "implement pagination") so callers can hand it
        straight to Django's own Paginator later.
        """
        content_type = TimelineService._content_type_for(obj)
        return TimelineEntry.objects.filter(
            content_type=content_type, object_id=obj.pk
        ).select_related("actor")

    @staticmethod
    def get_timeline_count(obj):
        return TimelineService.get_timeline(obj).count()
