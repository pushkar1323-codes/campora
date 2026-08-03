from django.test import TestCase
from django.urls import reverse

from accounts.models import StaffProfile, User
from admissions.models import Enquiry
from admissions.services import create_correction_request, resolve_correction_request
from communication.services import CommunicationService
from courses.models import College, Course

from .models import Notification
from .services import NotificationService


def _make_college_and_course(name="Test College", slug=None):
    college = College.objects.create(
        name=name, state="State", city="City", status=College.Status.APPROVED,
        **({"slug": slug} if slug else {}),
    )
    course = Course.objects.create(college=college, course_name="B.Tech CSE", duration="4 Years", eligibility="Class 12")
    return college, course


def _make_enquiry(course, submitted_by=None):
    return Enquiry.objects.create(
        full_name="Student One", father_name="F", email="s1@example.com", mobile="9999999999",
        address="Addr", dob="2000-01-01", gender="M", course=course,
        qualification="Class 12", percentage=80, admission_year=2026, submitted_by=submitted_by,
    )


class NotificationServiceTests(TestCase):
    """GenericForeignKey handling stays entirely internal to
    NotificationService -- these tests never touch ContentType/content_object
    directly, only pass plain model instances, same convention as
    timeline/communication/staff_notes's own service tests."""

    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.student = User.objects.create_user(username="student1", password="pass12345", role=User.Role.STUDENT)
        self.other_student = User.objects.create_user(username="student2", password="pass12345", role=User.Role.STUDENT)
        self.enquiry = _make_enquiry(self.course, submitted_by=self.student)

    def test_notify_creates_notification_for_recipient(self):
        notification = NotificationService.notify(
            self.student, notification_type="TEST_EVENT", title="Test Title",
            body="Test body", action_url="/somewhere/", obj=self.enquiry, college=self.college,
        )
        self.assertEqual(notification.recipient, self.student)
        self.assertEqual(notification.title, "Test Title")
        self.assertFalse(notification.is_read)
        self.assertEqual(notification.content_object, self.enquiry)

    def test_notify_is_noop_for_none_recipient(self):
        """A None recipient (e.g. an anonymous/guest enquiry's submitted_by)
        must be handled silently -- callers pass it unconditionally."""
        result = NotificationService.notify(None, notification_type="TEST_EVENT", title="Test")
        self.assertIsNone(result)
        self.assertEqual(Notification.objects.count(), 0)

    def test_notify_many_creates_one_per_recipient_and_dedupes(self):
        created = NotificationService.notify_many(
            [self.student, self.other_student, self.student, None],
            notification_type="TEST_EVENT", title="Broadcast",
        )
        self.assertEqual(Notification.objects.count(), 2)
        self.assertEqual(len(created), 2)

    def test_get_unread_count_only_counts_this_users_unread(self):
        NotificationService.notify(self.student, notification_type="A", title="A")
        NotificationService.notify(self.student, notification_type="B", title="B")
        NotificationService.notify(self.other_student, notification_type="C", title="C")
        self.assertEqual(NotificationService.get_unread_count(self.student), 2)
        self.assertEqual(NotificationService.get_unread_count(self.other_student), 1)

    def test_mark_read_sets_is_read_and_read_at(self):
        notification = NotificationService.notify(self.student, notification_type="A", title="A")
        self.assertIsNone(notification.read_at)
        NotificationService.mark_read(notification)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)

    def test_mark_all_read_only_affects_that_user(self):
        NotificationService.notify(self.student, notification_type="A", title="A")
        NotificationService.notify(self.student, notification_type="B", title="B")
        NotificationService.notify(self.other_student, notification_type="C", title="C")
        NotificationService.mark_all_read(self.student)
        self.assertEqual(NotificationService.get_unread_count(self.student), 0)
        self.assertEqual(NotificationService.get_unread_count(self.other_student), 1)

    def test_get_notifications_newest_first(self):
        n1 = NotificationService.notify(self.student, notification_type="A", title="First")
        n2 = NotificationService.notify(self.student, notification_type="B", title="Second")
        ordered = list(NotificationService.get_notifications(self.student))
        self.assertEqual(ordered, [n2, n1])


class NotificationViewTests(TestCase):
    """Ownership scoping: a Notification always belongs to exactly one
    recipient -- these tests confirm a user can never see or mark-read
    another user's notification, the same "never confirm existence of
    something out of scope" pattern used throughout this project."""

    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.student = User.objects.create_user(username="student1", password="pass12345", role=User.Role.STUDENT)
        self.other_student = User.objects.create_user(username="student2", password="pass12345", role=User.Role.STUDENT)

    def test_list_requires_login(self):
        response = self.client.get(reverse("notifications:list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_list_shows_only_own_notifications(self):
        NotificationService.notify(self.student, notification_type="A", title="Mine")
        NotificationService.notify(self.other_student, notification_type="B", title="Not Mine")
        self.client.login(username="student1", password="pass12345")
        response = self.client.get(reverse("notifications:list"))
        self.assertContains(response, "Mine")
        self.assertNotContains(response, "Not Mine")

    def test_mark_read_404s_for_another_users_notification(self):
        notification = NotificationService.notify(self.other_student, notification_type="A", title="Not Mine")
        self.client.login(username="student1", password="pass12345")
        response = self.client.get(reverse("notifications:mark_read", args=[notification.pk]))
        self.assertEqual(response.status_code, 404)
        notification.refresh_from_db()
        self.assertFalse(notification.is_read)

    def test_mark_read_marks_read_and_redirects_to_action_url(self):
        notification = NotificationService.notify(
            self.student, notification_type="A", title="Mine", action_url="/dashboard/",
        )
        self.client.login(username="student1", password="pass12345")
        response = self.client.get(reverse("notifications:mark_read", args=[notification.pk]))
        self.assertRedirects(response, "/dashboard/", fetch_redirect_response=False)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_mark_read_falls_back_to_list_when_no_action_url(self):
        notification = NotificationService.notify(self.student, notification_type="A", title="Mine")
        self.client.login(username="student1", password="pass12345")
        response = self.client.get(reverse("notifications:mark_read", args=[notification.pk]))
        self.assertRedirects(response, reverse("notifications:list"))

    def test_mark_all_read_only_marks_own(self):
        mine = NotificationService.notify(self.student, notification_type="A", title="Mine")
        theirs = NotificationService.notify(self.other_student, notification_type="B", title="Not Mine")
        self.client.login(username="student1", password="pass12345")
        self.client.post(reverse("notifications:mark_all_read"))
        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertTrue(mine.is_read)
        self.assertFalse(theirs.is_read)

    def test_unread_count_endpoint_returns_json(self):
        NotificationService.notify(self.student, notification_type="A", title="Mine")
        self.client.login(username="student1", password="pass12345")
        response = self.client.get(reverse("notifications:unread_count"))
        self.assertEqual(response.json(), {"unread_count": 1})

    def test_navbar_shows_bell_and_badge_for_authenticated_user(self):
        NotificationService.notify(self.student, notification_type="A", title="Ping")
        self.client.login(username="student1", password="pass12345")
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "notifBell")
        self.assertContains(response, "Ping")

    def test_navbar_has_no_bell_for_anonymous_user(self):
        response = self.client.get(reverse("core:home"))
        self.assertNotContains(response, "notifBell")


class NotificationTriggerIntegrationTests(TestCase):
    """Confirms the actual call sites wired into existing services/views
    (not just NotificationService in isolation) produce the right
    notification for the right recipient."""

    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF, is_staff=True)
        StaffProfile.objects.create(user=self.staff, college=self.college, designation="Staff")
        self.student = User.objects.create_user(username="student1", password="pass12345", role=User.Role.STUDENT)

    def test_enquiry_submission_notifies_college_staff(self):
        response = self.client.post(
            reverse("admissions:enquiry_create", args=[self.course.pk]),
            {
                "full_name": "New Student", "father_name": "F", "email": "new@example.com",
                "mobile": "9999999998", "address": "Addr", "dob": "2000-01-01", "gender": "M",
                "qualification": "Class 12", "percentage": "75", "admission_year": "2026",
            },
        )
        self.assertEqual(response.status_code, 302)
        notification = Notification.objects.get(recipient=self.staff)
        self.assertEqual(notification.notification_type, "ENQUIRY_SUBMITTED")
        self.assertFalse(notification.is_read)

    def test_staff_reply_notifies_student_owner(self):
        enquiry = _make_enquiry(self.course, submitted_by=self.student)
        self.client.login(username="staff1", password="pass12345")
        self.client.post(
            reverse("dashboard:enquiry_message_reply", args=[enquiry.pk]), {"content": "Please submit documents."},
        )
        notification = Notification.objects.get(recipient=self.student, notification_type="STAFF_REPLIED")
        self.assertIn(str(enquiry.pk), "" or notification.action_url)

    def test_staff_reply_is_noop_for_anonymous_guest_enquiry(self):
        """No crash, and no notification created, when the enquiry has no
        linked account (submitted_by=None)."""
        enquiry = _make_enquiry(self.course, submitted_by=None)
        self.client.login(username="staff1", password="pass12345")
        response = self.client.post(
            reverse("dashboard:enquiry_message_reply", args=[enquiry.pk]), {"content": "Hello"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Notification.objects.filter(notification_type="STAFF_REPLIED").count(), 0)

    def test_student_reply_notifies_engaged_staff_only(self):
        enquiry = _make_enquiry(self.course, submitted_by=self.student)
        # Staff must have engaged with the thread first (e.g. by viewing
        # the enquiry detail page) to become a participant.
        self.client.login(username="staff1", password="pass12345")
        self.client.get(reverse("dashboard:enquiry_detail", args=[enquiry.pk]))
        self.client.logout()

        self.client.login(username="student1", password="pass12345")
        self.client.post(
            reverse("admissions:enquiry_conversation", args=[enquiry.pk]), {"content": "Here are my documents."},
        )
        notification = Notification.objects.get(recipient=self.staff, notification_type="STUDENT_REPLIED")
        self.assertEqual(notification.recipient, self.staff)

    def test_correction_requested_notifies_student(self):
        enquiry = _make_enquiry(self.course, submitted_by=self.student)
        create_correction_request(enquiry, requested_by=self.staff, reason="Fix your phone number")
        notification = Notification.objects.get(recipient=self.student, notification_type="CORRECTION_REQUESTED")
        self.assertEqual(notification.body, "Fix your phone number")

    def test_correction_resolved_notifies_student(self):
        enquiry = _make_enquiry(self.course, submitted_by=self.student)
        correction = create_correction_request(enquiry, requested_by=self.staff, reason="Fix your phone number")
        Notification.objects.filter(recipient=self.student).delete()  # isolate the resolve-triggered one
        resolve_correction_request(correction, resolved_by=self.staff)
        notification = Notification.objects.get(recipient=self.student, notification_type="CORRECTION_RESOLVED")
        self.assertEqual(notification.title, "Your Correction Was Resolved")

    def test_enquiry_status_change_notifies_student_with_high_priority_on_admit(self):
        enquiry = _make_enquiry(self.course, submitted_by=self.student)
        self.client.login(username="staff1", password="pass12345")
        response = self.client.post(
            reverse("dashboard:enquiry_edit", args=[enquiry.pk]),
            {
                "full_name": enquiry.full_name, "father_name": enquiry.father_name, "email": enquiry.email,
                "mobile": enquiry.mobile, "address": enquiry.address, "dob": "2000-01-01", "gender": "M",
                "qualification": enquiry.qualification, "percentage": "80", "admission_year": "2026",
                "course": self.course.pk, "status": Enquiry.Status.ADMITTED,
            },
        )
        self.assertEqual(response.status_code, 302)
        notification = Notification.objects.get(recipient=self.student, notification_type=f"ENQUIRY_{Enquiry.Status.ADMITTED}")
        self.assertEqual(notification.priority, Notification.Priority.HIGH)

    def test_staff_reply_notifies_other_engaged_staff_participants_too(self):
        """Bugfix: staff replying previously only notified the student --
        another staff/admin already following the same enquiry (i.e. an
        active thread participant, same concept enquiry_conversation
        already used for student replies) never learned a colleague had
        replied at all."""
        enquiry = _make_enquiry(self.course, submitted_by=self.student)
        other_staff = User.objects.create_user(username="staff2", password="pass12345", role=User.Role.COLLEGE_ADMIN, is_staff=True)
        StaffProfile.objects.create(user=other_staff, college=self.college, designation="Admin")

        # Both staff members, AND the student, must have engaged with the
        # thread first to become participants (e.g. by viewing the
        # respective detail/conversation page) -- the student's own
        # participation here is what makes the double-notify guard below
        # actually meaningful to test (otherwise the student simply
        # wouldn't be in other_participants at all yet).
        self.client.login(username="staff1", password="pass12345")
        self.client.get(reverse("dashboard:enquiry_detail", args=[enquiry.pk]))
        self.client.logout()
        self.client.login(username="staff2", password="pass12345")
        self.client.get(reverse("dashboard:enquiry_detail", args=[enquiry.pk]))
        self.client.logout()
        self.client.login(username="student1", password="pass12345")
        self.client.get(reverse("admissions:enquiry_conversation", args=[enquiry.pk]))
        self.client.logout()

        # staff1 replies -- staff2 (a fellow participant) must be notified.
        self.client.login(username="staff1", password="pass12345")
        self.client.post(
            reverse("dashboard:enquiry_message_reply", args=[enquiry.pk]), {"content": "Please review this."},
        )
        self.assertTrue(
            Notification.objects.filter(recipient=other_staff, notification_type="STAFF_REPLIED").exists()
        )
        # The student is still notified too, exactly once (not double-notified
        # via both the explicit call and the other_participants loop).
        self.assertEqual(
            Notification.objects.filter(recipient=self.student, notification_type="STAFF_REPLIED").count(), 1,
        )
        # staff1 (the sender) never notifies themselves.
        self.assertFalse(
            Notification.objects.filter(recipient=self.staff, notification_type="STAFF_REPLIED").exists()
        )

    def test_contact_message_notifies_platform_admins_only(self):
        platform_admin = User.objects.create_user(
            username="padmin", password="pass12345", role=User.Role.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )
        response = self.client.post(
            reverse("core:contact"),
            {"full_name": "Visitor", "email": "visitor@example.com", "phone": "", "subject": "Question", "message": "Hi there, I have a question."},
        )
        self.assertEqual(response.status_code, 302)
        notification = Notification.objects.get(recipient=platform_admin, notification_type="CONTACT_MESSAGE_RECEIVED")
        self.assertIn("Question", notification.body)
        # College staff (not a Platform Admin) must never get this one.
        self.assertFalse(Notification.objects.filter(recipient=self.staff, notification_type="CONTACT_MESSAGE_RECEIVED").exists())
