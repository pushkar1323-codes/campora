from accounts.models import User
from courses.models import College, Course
from django.test import TestCase
from django.urls import reverse

from .models import ContactMessage
from .services import ContactService


class ContactServiceTests(TestCase):
    def test_create_message_persists(self):
        msg = ContactService.create_message(
            full_name="Jane Doe", email="jane@example.com", phone="9998887777",
            subject="Question about admissions", message="Hello, I have a question.",
        )
        self.assertTrue(ContactMessage.objects.filter(pk=msg.pk).exists())
        self.assertEqual(msg.status, ContactMessage.Status.NEW)

    def test_create_message_records_submitted_by_when_logged_in(self):
        user = User.objects.create_user(username="student1", password="pass12345", role=User.Role.STUDENT)
        msg = ContactService.create_message(
            full_name="Jane Doe", email="jane@example.com", phone="",
            subject="Q", message="Hello", submitted_by=user,
        )
        self.assertEqual(msg.submitted_by, user)

    def test_create_message_anonymous_has_no_submitted_by(self):
        msg = ContactService.create_message(
            full_name="Guest", email="guest@example.com", phone="", subject="Q", message="Hello",
        )
        self.assertIsNone(msg.submitted_by)

    def test_mark_read_transitions_new_to_read(self):
        admin = User.objects.create_user(username="padmin", password="pass12345", role=User.Role.SUPER_ADMIN)
        msg = ContactService.create_message(full_name="A", email="a@example.com", phone="", subject="Q", message="M")
        ContactService.mark_read(msg, read_by=admin)
        msg.refresh_from_db()
        self.assertEqual(msg.status, ContactMessage.Status.READ)
        self.assertEqual(msg.read_by, admin)
        self.assertIsNotNone(msg.read_at)

    def test_mark_read_does_not_downgrade_resolved(self):
        admin = User.objects.create_user(username="padmin", password="pass12345", role=User.Role.SUPER_ADMIN)
        msg = ContactService.create_message(full_name="A", email="a@example.com", phone="", subject="Q", message="M")
        ContactService.mark_resolved(msg, resolved_by=admin)
        ContactService.mark_read(msg, read_by=admin)
        msg.refresh_from_db()
        self.assertEqual(msg.status, ContactMessage.Status.RESOLVED)

    def test_mark_resolved_backfills_read_fields_if_skipped(self):
        admin = User.objects.create_user(username="padmin", password="pass12345", role=User.Role.SUPER_ADMIN)
        msg = ContactService.create_message(full_name="A", email="a@example.com", phone="", subject="Q", message="M")
        ContactService.mark_resolved(msg, resolved_by=admin)
        msg.refresh_from_db()
        self.assertEqual(msg.status, ContactMessage.Status.RESOLVED)
        self.assertIsNotNone(msg.read_at)
        self.assertEqual(msg.read_by, admin)
        self.assertIsNotNone(msg.resolved_at)
        self.assertEqual(msg.resolved_by, admin)

    def test_get_unread_count(self):
        ContactService.create_message(full_name="A", email="a@example.com", phone="", subject="Q1", message="M")
        ContactService.create_message(full_name="B", email="b@example.com", phone="", subject="Q2", message="M")
        self.assertEqual(ContactService.get_unread_count(), 2)
        admin = User.objects.create_user(username="padmin", password="pass12345", role=User.Role.SUPER_ADMIN)
        first = ContactMessage.objects.first()
        ContactService.mark_read(first, read_by=admin)
        self.assertEqual(ContactService.get_unread_count(), 1)

    def test_get_messages_filters_by_status(self):
        admin = User.objects.create_user(username="padmin", password="pass12345", role=User.Role.SUPER_ADMIN)
        m1 = ContactService.create_message(full_name="A", email="a@example.com", phone="", subject="Q1", message="M")
        ContactService.create_message(full_name="B", email="b@example.com", phone="", subject="Q2", message="M")
        ContactService.mark_read(m1, read_by=admin)
        self.assertEqual(ContactService.get_messages(status=ContactMessage.Status.NEW).count(), 1)
        self.assertEqual(ContactService.get_messages(status=ContactMessage.Status.READ).count(), 1)
        self.assertEqual(ContactService.get_messages().count(), 2)


class ContactViewFixTests(TestCase):
    """Regression tests for the actual bug reported: the Contact form
    previously logged and discarded every submission."""

    def test_contact_submission_now_persists_to_database(self):
        response = self.client.post(reverse("core:contact"), {
            "full_name": "Real Visitor", "email": "visitor@example.com", "phone": "9998887777",
            "subject": "General Question", "message": "Does this actually get saved now?",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ContactMessage.objects.filter(email="visitor@example.com", subject="General Question").exists()
        )

    def test_contact_submission_as_logged_in_student_records_submitted_by(self):
        student = User.objects.create_user(username="student1", password="pass12345", role=User.Role.STUDENT)
        self.client.login(username="student1", password="pass12345")
        self.client.post(reverse("core:contact"), {
            "full_name": "Student Name", "email": "student1@example.com", "phone": "",
            "subject": "Q", "message": "This is a message long enough to pass validation.",
        })
        msg = ContactMessage.objects.get(email="student1@example.com")
        self.assertEqual(msg.submitted_by, student)

    def test_invalid_submission_does_not_create_a_row(self):
        before = ContactMessage.objects.count()
        self.client.post(reverse("core:contact"), {
            "full_name": "", "email": "not-an-email", "subject": "", "message": "",
        })
        self.assertEqual(ContactMessage.objects.count(), before)


class ContactMessageDashboardViewTests(TestCase):
    """Feature: Platform-Admin-only dashboard inbox and triage actions."""

    def setUp(self):
        self.platform_admin = User.objects.create_user(
            username="padmin", password="pass12345", role=User.Role.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )
        self.college_admin = User.objects.create_user(
            username="cadmin", password="pass12345", role=User.Role.COLLEGE_ADMIN, is_staff=True,
        )
        self.student = User.objects.create_user(username="student1", password="pass12345", role=User.Role.STUDENT)
        self.msg = ContactService.create_message(
            full_name="Jane Doe", email="jane@example.com", phone="", subject="Test Subject", message="Test message body.",
        )

    def test_platform_admin_can_view_contact_messages(self):
        self.client.login(username="padmin", password="pass12345")
        response = self.client.get(reverse("dashboard:contact_messages"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Subject")

    def test_college_admin_cannot_view_contact_messages(self):
        self.client.login(username="cadmin", password="pass12345")
        response = self.client.get(reverse("dashboard:contact_messages"))
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_view_contact_messages(self):
        self.client.login(username="student1", password="pass12345")
        response = self.client.get(reverse("dashboard:contact_messages"))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("dashboard:contact_messages"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_platform_admin_can_mark_read(self):
        self.client.login(username="padmin", password="pass12345")
        response = self.client.post(reverse("dashboard:contact_message_mark_read", args=[self.msg.pk]))
        self.assertEqual(response.status_code, 302)
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, ContactMessage.Status.READ)

    def test_platform_admin_can_mark_resolved(self):
        self.client.login(username="padmin", password="pass12345")
        response = self.client.post(reverse("dashboard:contact_message_resolve", args=[self.msg.pk]))
        self.assertEqual(response.status_code, 302)
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, ContactMessage.Status.RESOLVED)

    def test_college_admin_cannot_mark_read_or_resolved(self):
        self.client.login(username="cadmin", password="pass12345")
        self.client.post(reverse("dashboard:contact_message_mark_read", args=[self.msg.pk]))
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, ContactMessage.Status.NEW)

    def test_status_filter_query_param(self):
        admin = self.platform_admin
        ContactService.mark_resolved(self.msg, resolved_by=admin)
        ContactService.create_message(full_name="B", email="b@example.com", phone="", subject="Unread One", message="M")
        self.client.login(username="padmin", password="pass12345")
        response = self.client.get(reverse("dashboard:contact_messages") + "?status=NEW")
        self.assertContains(response, "Unread One")
        self.assertNotContains(response, "Test Subject")

    def test_platform_dashboard_shows_unread_badge(self):
        self.client.login(username="padmin", password="pass12345")
        response = self.client.get(reverse("dashboard:platform"))
        self.assertContains(response, "Contact Messages")


class ContactMessageAdminIntegrationTests(TestCase):
    def setUp(self):
        self.platform_admin = User.objects.create_user(
            username="padmin", password="pass12345", role=User.Role.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )
        self.college_admin = User.objects.create_user(
            username="cadmin", password="pass12345", role=User.Role.COLLEGE_ADMIN, is_staff=True,
        )
        self.msg = ContactService.create_message(
            full_name="Jane Doe", email="jane@example.com", phone="", subject="Admin Panel Test", message="M",
        )

    def test_registered_and_visible_to_platform_admin(self):
        self.client.login(username="padmin", password="pass12345")
        response = self.client.get("/admin/core/contactmessage/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin Panel Test")

    def test_college_admin_blocked_from_contact_message_admin(self):
        """Platform-level data, not college-scoped -- College Admin should
        not see it in the Admin Panel either."""
        self.client.login(username="cadmin", password="pass12345")
        response = self.client.get("/admin/core/contactmessage/")
        self.assertNotEqual(response.status_code, 200)

    def test_cannot_add_or_delete_via_admin(self):
        self.client.login(username="padmin", password="pass12345")
        self.assertEqual(self.client.get("/admin/core/contactmessage/add/").status_code, 403)
        self.assertEqual(
            self.client.get(f"/admin/core/contactmessage/{self.msg.pk}/delete/").status_code, 403
        )


class ContactServiceReopenTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="padmin", password="pass12345", role=User.Role.SUPER_ADMIN)
        self.other_admin = User.objects.create_user(username="padmin2", password="pass12345", role=User.Role.SUPER_ADMIN)
        self.msg = ContactService.create_message(full_name="A", email="a@example.com", phone="", subject="Q", message="M")

    def test_reopen_reverts_resolved_to_read(self):
        ContactService.mark_resolved(self.msg, resolved_by=self.admin)
        ContactService.reopen(self.msg, reopened_by=self.other_admin)
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, ContactMessage.Status.READ)

    def test_reopen_preserves_resolved_history(self):
        """resolved_at/resolved_by are NOT cleared -- kept as a
        historical record of what happened, alongside the new
        reopened_at/reopened_by."""
        ContactService.mark_resolved(self.msg, resolved_by=self.admin)
        ContactService.reopen(self.msg, reopened_by=self.other_admin)
        self.msg.refresh_from_db()
        self.assertIsNotNone(self.msg.resolved_at)
        self.assertEqual(self.msg.resolved_by, self.admin)
        self.assertIsNotNone(self.msg.reopened_at)
        self.assertEqual(self.msg.reopened_by, self.other_admin)

    def test_reopen_is_a_noop_when_not_resolved(self):
        ContactService.reopen(self.msg, reopened_by=self.admin)
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, ContactMessage.Status.NEW)
        self.assertIsNone(self.msg.reopened_at)


class ContactMessageReplyViewTests(TestCase):
    """Reply reuses the existing Communication System -- verifies the
    reuse actually works end-to-end for this new owner type."""

    def setUp(self):
        self.platform_admin = User.objects.create_user(
            username="padmin", password="pass12345", role=User.Role.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )
        self.college_admin = User.objects.create_user(
            username="cadmin", password="pass12345", role=User.Role.COLLEGE_ADMIN, is_staff=True,
        )
        self.msg = ContactService.create_message(
            full_name="Jane Doe", email="jane@example.com", phone="", subject="Test Subject",
            message="This is the original message body.",
        )

    def test_platform_admin_can_view_detail_page(self):
        self.client.login(username="padmin", password="pass12345")
        response = self.client.get(reverse("dashboard:contact_message_detail", args=[self.msg.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This is the original message body.")

    def test_opening_detail_page_marks_new_message_as_read(self):
        self.client.login(username="padmin", password="pass12345")
        self.client.get(reverse("dashboard:contact_message_detail", args=[self.msg.pk]))
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, ContactMessage.Status.READ)

    def test_opening_detail_page_does_not_downgrade_resolved(self):
        self.client.login(username="padmin", password="pass12345")
        ContactService.mark_resolved(self.msg, resolved_by=self.platform_admin)
        self.client.get(reverse("dashboard:contact_message_detail", args=[self.msg.pk]))
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, ContactMessage.Status.RESOLVED)

    def test_platform_admin_can_reply(self):
        from communication.services import CommunicationService
        self.client.login(username="padmin", password="pass12345")
        response = self.client.post(
            reverse("dashboard:contact_message_reply", args=[self.msg.pk]),
            {"content": "Thanks for reaching out, here's an answer."},
        )
        self.assertEqual(response.status_code, 302)
        latest = CommunicationService.get_latest_message(self.msg)
        self.assertIsNotNone(latest)
        self.assertEqual(latest.content, "Thanks for reaching out, here's an answer.")
        self.assertEqual(latest.sender, self.platform_admin)

    def test_reply_appears_on_detail_page(self):
        self.client.login(username="padmin", password="pass12345")
        self.client.post(
            reverse("dashboard:contact_message_reply", args=[self.msg.pk]),
            {"content": "Thanks for reaching out, we have an answer for you."},
        )
        response = self.client.get(reverse("dashboard:contact_message_detail", args=[self.msg.pk]))
        self.assertContains(response, "Thanks for reaching out, we have an answer for you.")

    def test_college_admin_cannot_view_detail_or_reply(self):
        self.client.login(username="cadmin", password="pass12345")
        response = self.client.get(reverse("dashboard:contact_message_detail", args=[self.msg.pk]))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse("dashboard:contact_message_reply", args=[self.msg.pk]), {"content": "Not allowed here."}
        )
        self.assertEqual(response.status_code, 403)

    def test_reply_via_detail_page_form_also_works(self):
        """The detail page itself accepts a POST too (shares the reply
        form partial with the dedicated reply endpoint)."""
        from communication.services import CommunicationService
        self.client.login(username="padmin", password="pass12345")
        response = self.client.post(
            reverse("dashboard:contact_message_detail", args=[self.msg.pk]),
            {"content": "Replying directly from the detail page."},
        )
        self.assertEqual(response.status_code, 302)
        latest = CommunicationService.get_latest_message(self.msg)
        self.assertEqual(latest.content, "Replying directly from the detail page.")


class ContactMessageReopenViewTests(TestCase):
    def setUp(self):
        self.platform_admin = User.objects.create_user(
            username="padmin", password="pass12345", role=User.Role.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )
        self.college_admin = User.objects.create_user(
            username="cadmin", password="pass12345", role=User.Role.COLLEGE_ADMIN, is_staff=True,
        )
        self.msg = ContactService.create_message(full_name="A", email="a@example.com", phone="", subject="Q", message="M")
        ContactService.mark_resolved(self.msg, resolved_by=self.platform_admin)

    def test_platform_admin_can_reopen_a_mistakenly_resolved_message(self):
        self.client.login(username="padmin", password="pass12345")
        response = self.client.post(reverse("dashboard:contact_message_reopen", args=[self.msg.pk]))
        self.assertEqual(response.status_code, 302)
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, ContactMessage.Status.READ)

    def test_college_admin_cannot_reopen(self):
        self.client.login(username="cadmin", password="pass12345")
        response = self.client.post(reverse("dashboard:contact_message_reopen", args=[self.msg.pk]))
        self.assertEqual(response.status_code, 403)
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.status, ContactMessage.Status.RESOLVED)

    def test_reopen_link_appears_on_detail_page_for_resolved_message(self):
        self.client.login(username="padmin", password="pass12345")
        response = self.client.get(reverse("dashboard:contact_message_detail", args=[self.msg.pk]))
        self.assertContains(response, "Undo / Reopen")

    def test_reopen_link_hidden_for_non_resolved_message(self):
        other = ContactService.create_message(full_name="B", email="b@example.com", phone="", subject="Q2", message="M2")
        self.client.login(username="padmin", password="pass12345")
        response = self.client.get(reverse("dashboard:contact_message_detail", args=[other.pk]))
        self.assertNotContains(response, "Undo / Reopen")


class MessageEditDeleteRedirectDispatchTests(TestCase):
    """Regression test for the redirect-target bug found while wiring
    Contact Message replies into the shared Communication system:
    message_edit/message_delete used to hard-code a redirect to
    dashboard:enquiry_detail regardless of what the thread's owner
    actually was, which would have 404'd (or worse, loaded an unrelated
    Enquiry with a colliding pk) for a Contact-Message-owned reply."""

    def setUp(self):
        self.platform_admin = User.objects.create_user(
            username="padmin", password="pass12345", role=User.Role.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )
        self.msg = ContactService.create_message(full_name="A", email="a@example.com", phone="", subject="Q", message="M")

    def test_editing_a_contact_message_reply_redirects_to_contact_message_detail(self):
        from communication.services import CommunicationService
        reply = CommunicationService.post_message(self.msg, sender=self.platform_admin, content="Original reply text.")
        self.client.login(username="padmin", password="pass12345")
        response = self.client.post(
            reverse("dashboard:message_edit", args=[reply.pk]), {"content": "Updated reply text."}
        )
        self.assertRedirects(response, reverse("dashboard:contact_message_detail", args=[self.msg.pk]))

    def test_deleting_a_contact_message_reply_redirects_to_contact_message_detail(self):
        from communication.services import CommunicationService
        reply = CommunicationService.post_message(self.msg, sender=self.platform_admin, content="Reply to delete.")
        self.client.login(username="padmin", password="pass12345")
        response = self.client.post(reverse("dashboard:message_delete", args=[reply.pk]))
        self.assertRedirects(response, reverse("dashboard:contact_message_detail", args=[self.msg.pk]))
