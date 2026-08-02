"""
ContactService — the single entry point for creating and triaging
Contact Us submissions. Consistent with the service-layer pattern used
throughout this project (communication/staff_notes/timeline/audit
services): the view stays thin and just orchestrates; all persistence
and state-transition logic lives here.
"""
import logging

from django.utils import timezone

from .models import ContactMessage

logger = logging.getLogger(__name__)


class ContactService:
    """Stateless -- every method is a `@staticmethod`, same calling
    convention as every other service in this project.
    """

    @staticmethod
    def create_message(full_name, email, phone, subject, message, submitted_by=None):
        """Persist a new Contact Us submission. Previously this data
        was only ever written to the server log and then discarded --
        this is the fix: every submission is now a real, queryable row,
        visible to Platform Admin via the dashboard and Admin Panel.
        """
        contact_message = ContactMessage.objects.create(
            full_name=full_name, email=email, phone=phone,
            subject=subject, message=message, submitted_by=submitted_by,
        )
        logger.info(
            "Contact message #%s received from %s <%s>: %s",
            contact_message.pk, full_name, email, subject,
        )
        return contact_message

    @staticmethod
    def mark_read(contact_message, read_by):
        """Feature: triage. Only moves NEW -> READ -- never demotes an
        already-RESOLVED message back to READ (see mark_resolved)."""
        if contact_message.status == ContactMessage.Status.NEW:
            contact_message.status = ContactMessage.Status.READ
            contact_message.read_at = timezone.now()
            contact_message.read_by = read_by
            contact_message.save(update_fields=["status", "read_at", "read_by"])
        return contact_message

    @staticmethod
    def mark_resolved(contact_message, resolved_by):
        """Closes the loop -- e.g. after the Platform Admin has replied
        by email outside the system. Also backfills read_at/read_by if
        the message is being resolved directly without an intermediate
        "mark read" step.
        """
        if contact_message.status == ContactMessage.Status.NEW:
            contact_message.read_at = timezone.now()
            contact_message.read_by = resolved_by
        contact_message.status = ContactMessage.Status.RESOLVED
        contact_message.resolved_at = timezone.now()
        contact_message.resolved_by = resolved_by
        contact_message.save(update_fields=["status", "read_at", "read_by", "resolved_at", "resolved_by"])
        return contact_message

    @staticmethod
    def reopen(contact_message, reopened_by):
        """Undo an accidental 'Mark Resolved'. Reverts to READ, not NEW
        -- the message has clearly already been seen/handled once, so
        NEW would misrepresent it as never having been opened.
        resolved_at/resolved_by are deliberately left untouched (kept as
        a historical record of what happened, same reasoning as
        staff_notes.StaffNoteService.restore_note's audit trail) --
        reopened_at/reopened_by record the undo itself alongside them.
        A no-op if the message isn't actually RESOLVED.
        """
        if contact_message.status != ContactMessage.Status.RESOLVED:
            return contact_message
        contact_message.status = ContactMessage.Status.READ
        contact_message.reopened_at = timezone.now()
        contact_message.reopened_by = reopened_by
        contact_message.save(update_fields=["status", "reopened_at", "reopened_by"])
        return contact_message

    @staticmethod
    def get_messages(status=None):
        """Pagination-ready (unsliced) queryset, newest first (Model.Meta.ordering)."""
        qs = ContactMessage.objects.select_related("submitted_by", "read_by", "resolved_by", "reopened_by")
        if status:
            qs = qs.filter(status=status)
        return qs

    @staticmethod
    def get_unread_count():
        """For a future dashboard/nav badge -- counts NEW (not yet even
        opened) messages."""
        return ContactMessage.objects.filter(status=ContactMessage.Status.NEW).count()
