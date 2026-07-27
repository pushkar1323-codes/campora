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
