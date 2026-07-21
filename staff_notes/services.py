"""
StaffNoteService — the single entry point every other app uses to work
with Internal Staff Notes.

Same architectural rule as communication/services.py: no other app,
view, or form may import ContentType, GenericForeignKey, or touch
StaffNote.content_type/object_id directly. Every caller passes a plain
model instance (e.g. an admissions.Enquiry) and this service resolves
the generic relation internally.
"""
from django.utils import timezone

from .models import StaffNote


class StaffNoteService:
    """Stateless — every method is a `@staticmethod`, same calling
    convention as communication.services.CommunicationService.
    """

    @staticmethod
    def _content_type_for(obj):
        from django.contrib.contenttypes.models import ContentType
        return ContentType.objects.get_for_model(type(obj))

    @staticmethod
    def create_note(obj, author, content, author_role="", metadata=None):
        """Feature 1/2/3: create a private staff note on `obj`."""
        content_type = StaffNoteService._content_type_for(obj)
        resolved_role = author_role or getattr(author, "get_role_display", lambda: "")()
        return StaffNote.objects.create(
            content_type=content_type, object_id=obj.pk,
            author=author, author_role=resolved_role,
            content=content, metadata=metadata or {},
        )

    @staticmethod
    def edit_note(note, new_content, edited_by):
        """Feature 3: optional editing, no version history kept (same
        rule as communication.Message) -- just an `is_edited` flag and
        the normal `updated_at` auto-refresh. Permission (author-only, or
        Platform Admin, per Feature 4) is enforced by the caller via
        staff_notes.permissions.can_edit_note before this is called.
        """
        note.content = new_content
        note.is_edited = True
        note.save(update_fields=["content", "is_edited", "updated_at"])
        return note

    @staticmethod
    def delete_note(note, deleted_by):
        """Feature 3: soft delete only -- never removes the row."""
        note.is_deleted = True
        note.deleted_at = timezone.now()
        note.deleted_by = deleted_by
        note.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])
        return note

    @staticmethod
    def restore_note(note, restored_by):
        """Feature 3: Administrator-only restore (enforced by the caller
        via staff_notes.permissions.can_restore_note, not here)."""
        note.is_deleted = False
        note.restored_at = timezone.now()
        note.restored_by = restored_by
        note.save(update_fields=["is_deleted", "restored_at", "restored_by", "updated_at"])
        return note

    @staticmethod
    def get_notes(obj, include_deleted=False):
        """Reverse-chronological (Model.Meta.ordering), select_related
        queryset -- deliberately not sliced/paginated (Feature 8:
        "pagination-ready architecture") so callers can hand it straight
        to Django's own Paginator.
        """
        content_type = StaffNoteService._content_type_for(obj)
        qs = StaffNote.objects.filter(content_type=content_type, object_id=obj.pk).select_related(
            "author", "deleted_by", "restored_by"
        )
        if not include_deleted:
            qs = qs.filter(is_deleted=False)
        return qs

    @staticmethod
    def get_note_count(obj, include_deleted=False):
        return StaffNoteService.get_notes(obj, include_deleted=include_deleted).count()

    @staticmethod
    def search_notes(obj, query, include_deleted=False):
        """Feature 7 ("search-ready", not "search implemented"): a plain
        case-insensitive substring match today, same reasoning as
        communication.services.CommunicationService.search_messages.
        """
        if not query:
            return StaffNoteService.get_notes(obj, include_deleted=include_deleted)
        return StaffNoteService.get_notes(obj, include_deleted=include_deleted).filter(content__icontains=query)
