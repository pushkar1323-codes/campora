"""
CommunicationService — the single entry point every other app uses to
work with threads and messages.

Architectural rule (non-negotiable per this phase's instructions): NO
other app, view, or form may import ContentType, GenericForeignKey, or
touch MessageThread.content_type/object_id directly. Every caller passes
a plain model instance (e.g. an admissions.Enquiry, or a future
HostelApplication) and this service resolves the generic relation
internally. That's what keeps this whole module reusable across future
domains without redesign.

Event-readiness (architectural improvement #6): every state-changing
method below is a single, named, already-isolated function
(post_message, post_system_message, mark_thread_read, edit_message,
delete_message). The Event Framework itself is explicitly a later phase
and is NOT implemented here — but because every mutation already funnels
through one of these named calls (never ad hoc `Message.objects.create()`
scattered across the codebase), a future Event Publisher can be added by
having these functions additionally call `publish(...)` at the end, with
no change needed to any caller (admissions/dashboard) and no change to
the call sites shown in this phase's diagram:

    CorrectionRequest -> CommunicationService.post_system_message() -> (future) Event Publisher
"""
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q
from django.utils import timezone

from .models import Message, MessageThread, ThreadParticipant


class CommunicationService:
    """Stateless — every method is a `@staticmethod` operating on
    whatever `obj`/`thread`/`message` is passed in. No instance state,
    consistent with admissions/services.py's plain-function style; a
    class is used here (rather than module-level functions) purely
    because the calling convention requested is `CommunicationService.foo()`.
    """

    # -- Thread lookup / creation ----------------------------------------

    @staticmethod
    def _content_type_for(obj):
        return ContentType.objects.get_for_model(type(obj))

    @staticmethod
    def get_thread_for_object(obj):
        """Returns the MessageThread for `obj`, or None if one hasn't
        been created yet. Read-only — never creates."""
        content_type = CommunicationService._content_type_for(obj)
        return MessageThread.objects.filter(content_type=content_type, object_id=obj.pk).first()

    @staticmethod
    def create_thread_if_missing(obj):
        """Get-or-create a MessageThread for `obj`. Safe to call on every
        request that touches a thread (views do, at the top of every
        conversation-related view) — idempotent, and race-safe via the
        model's UniqueConstraint.
        """
        content_type = CommunicationService._content_type_for(obj)
        thread, _created = MessageThread.objects.get_or_create(
            content_type=content_type, object_id=obj.pk
        )
        return thread

    # -- Participants -----------------------------------------------------

    @staticmethod
    def add_participant(obj, user, role_label=""):
        """Adds `user` to `obj`'s thread (creating the thread if needed),
        or reactivates them if they'd previously been removed. The
        calling app decides *who* should be a participant and *what*
        role_label to use — this service has no domain knowledge of what
        "the student" or "college staff" means for any particular object
        type.
        """
        thread = CommunicationService.create_thread_if_missing(obj)
        participant, created = ThreadParticipant.objects.get_or_create(
            thread=thread, user=user, defaults={"role_label": role_label, "is_active": True},
        )
        if not created and (not participant.is_active or (role_label and participant.role_label != role_label)):
            participant.is_active = True
            if role_label:
                participant.role_label = role_label
            participant.save(update_fields=["is_active", "role_label"])
        return participant

    @staticmethod
    def remove_participant(obj, user):
        """Soft-removes `user` from `obj`'s thread (is_active=False), not
        a hard delete — not wired to any UI this phase, but exposed for
        forward compatibility (e.g. a future "remove participant" action)."""
        thread = CommunicationService.get_thread_for_object(obj)
        if thread is None:
            return
        ThreadParticipant.objects.filter(thread=thread, user=user).update(is_active=False)

    @staticmethod
    def get_participants(obj, active_only=True):
        thread = CommunicationService.get_thread_for_object(obj)
        if thread is None:
            return ThreadParticipant.objects.none()
        qs = thread.participants.select_related("user")
        if active_only:
            qs = qs.filter(is_active=True)
        return qs

    @staticmethod
    def is_participant(obj, user):
        return CommunicationService.get_participants(obj, active_only=True).filter(user=user).exists()

    # -- Posting messages ---------------------------------------------------

    @staticmethod
    def post_message(obj, sender, content, message_type=Message.Type.USER, sender_role="", metadata=None):
        """Feature 1/2: post a normal (or CORRECTION_REQUEST-typed) user
        message into `obj`'s thread. The sender is automatically added as
        an active participant (Feature: ThreadParticipant) — "whoever
        posts is part of the conversation" is a generic rule this service
        can own without any domain knowledge.
        """
        thread = CommunicationService.create_thread_if_missing(obj)
        resolved_role = sender_role or getattr(sender, "get_role_display", lambda: "")()
        CommunicationService.add_participant(obj, sender, role_label=resolved_role)
        return Message.objects.create(
            thread=thread, sender=sender, sender_role=resolved_role,
            message_type=message_type, content=content, metadata=metadata or {},
        )

    @staticmethod
    def post_system_message(obj, content, message_type=Message.Type.SYSTEM, metadata=None):
        """Feature 4: an automatic, sender-less message (e.g. triggered by
        admissions.services.create_correction_request). Displayed
        differently from user messages via `Message.is_system_generated`
        — see templates/communication/_message_list.html.
        """
        thread = CommunicationService.create_thread_if_missing(obj)
        return Message.objects.create(
            thread=thread, sender=None, sender_role="System",
            message_type=message_type, content=content, metadata=metadata or {},
        )

    # -- Editing / deleting -------------------------------------------------

    @staticmethod
    def edit_message(message, new_content, edited_by):
        """Feature 6: optional editing. No version history kept (per
        spec) — just an `is_edited` flag and the normal `updated_at`
        auto-refresh. Permission (only the sender, or Platform Admin, and
        never a system message) is enforced by the caller via
        communication.permissions.can_edit_message before this is
        called — this method assumes that check already passed.
        """
        message.content = new_content
        message.is_edited = True
        message.save(update_fields=["content", "is_edited", "updated_at"])
        return message

    @staticmethod
    def delete_message(message, deleted_by):
        """Feature 7: soft delete only — never removes the row. Records
        deleted_at/deleted_by (architectural improvement #3) for
        auditability beyond the plain is_deleted flag the original spec
        asked for.
        """
        message.is_deleted = True
        message.deleted_at = timezone.now()
        message.deleted_by = deleted_by
        message.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])
        return message

    # -- Read status ----------------------------------------------------------

    @staticmethod
    def mark_thread_read(obj, reader):
        """Feature 5: marks every not-yet-read message in `obj`'s thread
        that wasn't sent by `reader` (including sender-less system
        messages) as read. Returns how many messages were updated.

        NOTE the NULL-sender subtlety: `.exclude(sender=reader)` alone
        would silently drop every system message (sender IS NULL) from
        the result, because SQL's three-valued logic treats
        `NOT (NULL = X)` as unknown, not true — the row would never come
        back from `.exclude()`. The explicit `Q(sender__isnull=True) | ~Q(sender=reader)`
        below is required to include those rows too.
        """
        thread = CommunicationService.get_thread_for_object(obj)
        if thread is None:
            return 0
        unread = thread.messages.filter(is_deleted=False, is_read=False).filter(
            Q(sender__isnull=True) | ~Q(sender=reader)
        )
        count = unread.count()
        unread.update(is_read=True, read_at=timezone.now())
        return count

    @staticmethod
    def get_unread_count(obj, user):
        """Reusable helper (architectural improvement #7) for future
        dashboard badges: how many messages in `obj`'s thread are unread
        from `user`'s point of view. Same NULL-sender handling as
        mark_thread_read above.
        """
        thread = CommunicationService.get_thread_for_object(obj)
        if thread is None:
            return 0
        return thread.messages.filter(is_deleted=False, is_read=False).filter(
            Q(sender__isnull=True) | ~Q(sender=user)
        ).count()

    @staticmethod
    def get_unread_counts_bulk(model_class, object_ids, user):
        """Phase 2B, Feature 6/8: the list-view counterpart of
        get_unread_count above. A paginated list of enquiries (or any
        other object type) showing an "unread" badge per row must NOT
        call get_unread_count() once per row -- that's exactly the N+1
        pattern Feature 8 asks to avoid. This does it in a single query
        for the whole page instead, returning {object_id: count}
        (objects with no unread messages, or no thread at all, are simply
        absent from the dict -- callers should default missing keys to 0).
        """
        if not object_ids:
            return {}
        content_type = ContentType.objects.get_for_model(model_class)
        rows = (
            Message.objects.filter(
                thread__content_type=content_type, thread__object_id__in=object_ids,
                is_deleted=False, is_read=False,
            )
            .filter(Q(sender__isnull=True) | ~Q(sender=user))
            .values("thread__object_id")
            .annotate(count=Count("id"))
        )
        return {row["thread__object_id"]: row["count"] for row in rows}

    # -- Reading messages -----------------------------------------------------

    @staticmethod
    def get_messages(obj, include_deleted=False):
        """Chronologically-ordered (Model.Meta.ordering), select_related
        queryset — deliberately NOT sliced/paginated here (architectural
        improvement #7: "pagination-ready querysets") so callers can hand
        it straight to Django's own Paginator.
        """
        thread = CommunicationService.get_thread_for_object(obj)
        if thread is None:
            return Message.objects.none()
        qs = thread.messages.select_related("sender", "deleted_by")
        if not include_deleted:
            qs = qs.filter(is_deleted=False)
        return qs

    @staticmethod
    def get_latest_message(obj, include_deleted=False):
        return CommunicationService.get_messages(obj, include_deleted=include_deleted).last()

    @staticmethod
    def search_messages(obj, query, include_deleted=False):
        """Feature 9 ("search-ready", not "search implemented" this
        phase): a plain case-insensitive substring match today. See the
        note in Message.Meta about why a proper full-text/prefix index
        isn't added speculatively yet.
        """
        if not query:
            return CommunicationService.get_messages(obj, include_deleted=include_deleted)
        return CommunicationService.get_messages(obj, include_deleted=include_deleted).filter(
            content__icontains=query
        )
