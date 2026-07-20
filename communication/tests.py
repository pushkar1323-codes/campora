from django.test import TestCase

from accounts.models import User
from courses.models import College, Course

from .models import Message, MessageThread, ThreadParticipant
from .permissions import can_delete_message, can_edit_message, can_send_message, can_view_thread
from .services import CommunicationService


def _make_college_and_course(name="Test College", slug=None):
    college = College.objects.create(
        name=name, state="State", city="City", status=College.Status.APPROVED,
        **({"slug": slug} if slug else {}),
    )
    course = Course.objects.create(college=college, course_name="B.Tech CSE", duration="4 Years", eligibility="Class 12")
    return college, course


class CommunicationServiceThreadTests(TestCase):
    """Verifies GenericForeignKey handling stays entirely internal to
    CommunicationService -- these tests never touch ContentType/
    content_object directly, only pass plain model instances, exactly
    like a real caller (admissions/dashboard) would."""

    def setUp(self):
        self.college, self.course = _make_college_and_course()

    def test_get_thread_for_object_returns_none_before_creation(self):
        self.assertIsNone(CommunicationService.get_thread_for_object(self.course))

    def test_create_thread_if_missing_is_idempotent(self):
        thread1 = CommunicationService.create_thread_if_missing(self.course)
        thread2 = CommunicationService.create_thread_if_missing(self.course)
        self.assertEqual(thread1.pk, thread2.pk)
        self.assertEqual(MessageThread.objects.count(), 1)

    def test_threads_for_different_objects_are_independent(self):
        college2, course2 = _make_college_and_course(name="Other College", slug="other-college-comm-test")
        thread_a = CommunicationService.create_thread_if_missing(self.course)
        thread_b = CommunicationService.create_thread_if_missing(course2)
        self.assertNotEqual(thread_a.pk, thread_b.pk)


class CommunicationServiceParticipantTests(TestCase):
    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.student = User.objects.create_user(username="student1", password="pass12345", role=User.Role.STUDENT)

    def test_add_participant_creates_row(self):
        participant = CommunicationService.add_participant(self.course, self.student, role_label="Student")
        self.assertIsInstance(participant, ThreadParticipant)
        self.assertTrue(participant.is_active)
        self.assertEqual(participant.role_label, "Student")

    def test_add_participant_is_idempotent(self):
        CommunicationService.add_participant(self.course, self.student, role_label="Student")
        CommunicationService.add_participant(self.course, self.student, role_label="Student")
        self.assertEqual(ThreadParticipant.objects.count(), 1)

    def test_remove_then_add_participant_reactivates(self):
        CommunicationService.add_participant(self.course, self.student, role_label="Student")
        CommunicationService.remove_participant(self.course, self.student)
        self.assertFalse(CommunicationService.is_participant(self.course, self.student))
        CommunicationService.add_participant(self.course, self.student, role_label="Student")
        self.assertTrue(CommunicationService.is_participant(self.course, self.student))
        self.assertEqual(ThreadParticipant.objects.count(), 1)

    def test_post_message_auto_adds_sender_as_participant(self):
        self.assertFalse(CommunicationService.is_participant(self.course, self.student))
        CommunicationService.post_message(self.course, sender=self.student, content="Hello")
        self.assertTrue(CommunicationService.is_participant(self.course, self.student))


class CommunicationServiceMessageTests(TestCase):
    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.student = User.objects.create_user(username="student1", password="pass12345", role=User.Role.STUDENT)
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF)

    def test_post_message_creates_user_message(self):
        message = CommunicationService.post_message(self.course, sender=self.student, content="Hi there")
        self.assertEqual(message.message_type, Message.Type.USER)
        self.assertEqual(message.content, "Hi there")
        self.assertEqual(message.sender, self.student)

    def test_post_system_message_has_no_sender(self):
        message = CommunicationService.post_system_message(self.course, content="Enquiry submitted.")
        self.assertIsNone(message.sender)
        self.assertEqual(message.message_type, Message.Type.SYSTEM)
        self.assertTrue(message.is_system_generated)

    def test_messages_ordered_chronologically(self):
        m1 = CommunicationService.post_message(self.course, sender=self.student, content="First")
        m2 = CommunicationService.post_message(self.course, sender=self.staff, content="Second")
        ordered = list(CommunicationService.get_messages(self.course))
        self.assertEqual(ordered, [m1, m2])

    def test_get_messages_excludes_deleted_by_default(self):
        message = CommunicationService.post_message(self.course, sender=self.student, content="Delete me")
        CommunicationService.delete_message(message, deleted_by=self.student)
        self.assertEqual(CommunicationService.get_messages(self.course).count(), 0)
        self.assertEqual(CommunicationService.get_messages(self.course, include_deleted=True).count(), 1)

    def test_edit_message_sets_is_edited(self):
        message = CommunicationService.post_message(self.course, sender=self.student, content="Original")
        CommunicationService.edit_message(message, "Updated", edited_by=self.student)
        message.refresh_from_db()
        self.assertEqual(message.content, "Updated")
        self.assertTrue(message.is_edited)

    def test_delete_message_is_soft_delete_with_audit_metadata(self):
        message = CommunicationService.post_message(self.course, sender=self.student, content="Bye")
        CommunicationService.delete_message(message, deleted_by=self.staff)
        message.refresh_from_db()
        self.assertTrue(message.is_deleted)
        self.assertIsNotNone(message.deleted_at)
        self.assertEqual(message.deleted_by, self.staff)
        # never a hard delete
        self.assertTrue(Message.objects.filter(pk=message.pk).exists())

    def test_search_messages_case_insensitive_substring(self):
        CommunicationService.post_message(self.course, sender=self.student, content="Please verify my marksheet")
        CommunicationService.post_message(self.course, sender=self.staff, content="Documents received")
        results = CommunicationService.search_messages(self.course, "MARKSHEET")
        self.assertEqual(results.count(), 1)


class CommunicationServiceReadStatusTests(TestCase):
    """Also exercises the NULL-sender subtlety documented in
    CommunicationService.mark_thread_read/get_unread_count."""

    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.student = User.objects.create_user(username="student1", password="pass12345", role=User.Role.STUDENT)
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF)

    def test_unread_count_counts_others_messages(self):
        CommunicationService.post_message(self.course, sender=self.staff, content="From staff")
        self.assertEqual(CommunicationService.get_unread_count(self.course, self.student), 1)
        self.assertEqual(CommunicationService.get_unread_count(self.course, self.staff), 0)

    def test_unread_count_includes_system_messages(self):
        CommunicationService.post_system_message(self.course, content="System notice")
        self.assertEqual(CommunicationService.get_unread_count(self.course, self.student), 1)
        self.assertEqual(CommunicationService.get_unread_count(self.course, self.staff), 1)

    def test_mark_thread_read_marks_others_and_system_messages_only(self):
        CommunicationService.post_message(self.course, sender=self.staff, content="From staff")
        CommunicationService.post_system_message(self.course, content="System notice")
        own_message = CommunicationService.post_message(self.course, sender=self.student, content="From me")

        updated = CommunicationService.mark_thread_read(self.course, self.student)
        self.assertEqual(updated, 2)  # staff message + system message, not own
        self.assertEqual(CommunicationService.get_unread_count(self.course, self.student), 0)
        own_message.refresh_from_db()
        self.assertFalse(own_message.is_read)  # own message never auto-marked read


class CommunicationPermissionsTests(TestCase):
    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.student = User.objects.create_user(username="student1", password="pass12345", role=User.Role.STUDENT)
        self.other_student = User.objects.create_user(username="student2", password="pass12345", role=User.Role.STUDENT)
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF)
        self.platform_admin = User.objects.create_user(
            username="padmin", password="pass12345", role=User.Role.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )

    def test_non_participant_cannot_view_or_send(self):
        CommunicationService.add_participant(self.course, self.student, role_label="Student")
        self.assertFalse(can_view_thread(self.other_student, self.course))
        self.assertFalse(can_send_message(self.other_student, self.course))

    def test_participant_can_view_and_send(self):
        CommunicationService.add_participant(self.course, self.student, role_label="Student")
        self.assertTrue(can_view_thread(self.student, self.course))
        self.assertTrue(can_send_message(self.student, self.course))

    def test_platform_admin_always_has_full_access(self):
        self.assertTrue(can_view_thread(self.platform_admin, self.course))
        self.assertTrue(can_send_message(self.platform_admin, self.course))

    def test_only_sender_can_edit_own_message(self):
        message = CommunicationService.post_message(self.course, sender=self.student, content="Hi")
        self.assertTrue(can_edit_message(self.student, message))
        self.assertFalse(can_edit_message(self.staff, message))
        self.assertTrue(can_edit_message(self.platform_admin, message))

    def test_system_messages_are_never_editable_or_deletable(self):
        message = CommunicationService.post_system_message(self.course, content="System notice")
        self.assertFalse(can_edit_message(self.platform_admin, message))
        self.assertFalse(can_delete_message(self.platform_admin, message))

    def test_deleted_message_is_never_editable_or_deletable_again(self):
        message = CommunicationService.post_message(self.course, sender=self.student, content="Hi")
        CommunicationService.delete_message(message, deleted_by=self.student)
        self.assertFalse(can_edit_message(self.student, message))
        self.assertFalse(can_delete_message(self.student, message))

    def test_sender_can_delete_own_message(self):
        message = CommunicationService.post_message(self.course, sender=self.student, content="Hi")
        self.assertTrue(can_delete_message(self.student, message))
        self.assertFalse(can_delete_message(self.staff, message))
