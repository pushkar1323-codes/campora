"""
NotificationService — the single entry point every other app uses to
publish and read notifications. See notifications/models.py's module
docstring for the full architectural rationale.

Same rule as communication/timeline/staff_notes: no other app, view, or
form may import ContentType/GenericForeignKey or touch
Notification.content_type/object_id directly.
"""
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .models import Notification


class NotificationService:
    """Stateless — every method is a @staticmethod, same calling
    convention as CommunicationService/TimelineService/StaffNoteService/
    AuditService/ContactService.
    """

    @staticmethod
    def _content_type_for(obj):
        return ContentType.objects.get_for_model(type(obj)) if obj is not None else None

    @staticmethod
    def notify(recipient, notification_type, title, body="", action_url="",
               priority=Notification.Priority.NORMAL, obj=None, college=None):
        """Create one Notification for one recipient.

        A no-op (returns None) if `recipient` is falsy — this lets every
        call site pass a possibly-None owner (e.g. an anonymous/guest
        Enquiry's `submitted_by`) unconditionally, without an `if user:`
        guard duplicated at every trigger point.
        """
        if not recipient:
            return None
        content_type = NotificationService._content_type_for(obj)
        return Notification.objects.create(
            recipient=recipient, notification_type=notification_type,
            title=title, body=body, action_url=action_url, priority=priority,
            content_type=content_type, object_id=(obj.pk if obj is not None else None),
            college=college,
        )

    @staticmethod
    def notify_many(recipients, notification_type, title, body="", action_url="",
                     priority=Notification.Priority.NORMAL, obj=None, college=None):
        """Same as notify(), for an iterable/queryset of recipients — e.g.
        every College Staff/Admin at a college when a new enquiry comes in.
        Silently skips falsy entries and de-duplicates by user id so the
        same person is never notified twice for one event.
        """
        seen = set()
        created = []
        for recipient in recipients:
            if not recipient or recipient.pk in seen:
                continue
            seen.add(recipient.pk)
            created.append(
                NotificationService.notify(
                    recipient, notification_type, title, body=body, action_url=action_url,
                    priority=priority, obj=obj, college=college,
                )
            )
        return created

    @staticmethod
    def get_notifications(user, unread_only=False):
        """Pagination-ready (unsliced) queryset, newest first
        (Model.Meta.ordering) — callers can hand it straight to Django's
        own Paginator, or slice it directly for a small "recent" preview.
        """
        qs = Notification.objects.filter(recipient=user)
        if unread_only:
            qs = qs.filter(is_read=False)
        return qs

    @staticmethod
    def get_unread_count(user):
        return Notification.objects.filter(recipient=user, is_read=False).count()

    @staticmethod
    def mark_read(notification):
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])
        return notification

    @staticmethod
    def mark_all_read(user):
        """Single bulk UPDATE, not a per-row loop — this is a genuine bulk
        state change (unlike mark_read's single-row save()), and Django's
        auto_now-style tracking isn't in play here (read_at is set
        explicitly), so a plain queryset .update() is both correct and
        efficient.
        """
        return Notification.objects.filter(recipient=user, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
