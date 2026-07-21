from accounts.models import User
from courses.models import College, Course
from django.test import TestCase

from .models import StaffNote
from .permissions import can_create_note, can_delete_note, can_edit_note, can_restore_note, can_view_notes
from .services import StaffNoteService


def _make_college_and_course(name="Test College", slug=None):
    college = College.objects.create(
        name=name, state="State", city="City", status=College.Status.APPROVED,
        **({"slug": slug} if slug else {}),
    )
    course = Course.objects.create(college=college, course_name="B.Tech CSE", duration="4 Years", eligibility="Class 12")
    return college, course


class StaffNoteServiceTests(TestCase):
    """GenericForeignKey handling stays entirely internal to
    StaffNoteService -- these tests never touch ContentType/
    content_object directly, only pass plain model instances."""

    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF)
        self.admin = User.objects.create_user(username="admin1", password="pass12345", role=User.Role.COLLEGE_ADMIN)

    def test_create_note(self):
        note = StaffNoteService.create_note(self.course, author=self.staff, content="Waiting for certificate.")
        self.assertEqual(note.content, "Waiting for certificate.")
        self.assertEqual(note.author, self.staff)
        self.assertFalse(note.is_deleted)

    def test_notes_ordered_most_recent_first(self):
        n1 = StaffNoteService.create_note(self.course, author=self.staff, content="First")
        n2 = StaffNoteService.create_note(self.course, author=self.staff, content="Second")
        ordered = list(StaffNoteService.get_notes(self.course))
        self.assertEqual(ordered, [n2, n1])

    def test_get_notes_excludes_deleted_by_default(self):
        note = StaffNoteService.create_note(self.course, author=self.staff, content="Delete me")
        StaffNoteService.delete_note(note, deleted_by=self.staff)
        self.assertEqual(StaffNoteService.get_notes(self.course).count(), 0)
        self.assertEqual(StaffNoteService.get_notes(self.course, include_deleted=True).count(), 1)

    def test_edit_note_sets_is_edited(self):
        note = StaffNoteService.create_note(self.course, author=self.staff, content="Original")
        StaffNoteService.edit_note(note, "Updated", edited_by=self.staff)
        note.refresh_from_db()
        self.assertEqual(note.content, "Updated")
        self.assertTrue(note.is_edited)

    def test_delete_note_is_soft_delete_with_audit_metadata(self):
        note = StaffNoteService.create_note(self.course, author=self.staff, content="Bye")
        StaffNoteService.delete_note(note, deleted_by=self.admin)
        note.refresh_from_db()
        self.assertTrue(note.is_deleted)
        self.assertIsNotNone(note.deleted_at)
        self.assertEqual(note.deleted_by, self.admin)
        self.assertTrue(StaffNote.objects.filter(pk=note.pk).exists())  # never a hard delete

    def test_restore_note(self):
        note = StaffNoteService.create_note(self.course, author=self.staff, content="Bye")
        StaffNoteService.delete_note(note, deleted_by=self.admin)
        StaffNoteService.restore_note(note, restored_by=self.admin)
        note.refresh_from_db()
        self.assertFalse(note.is_deleted)
        self.assertEqual(note.restored_by, self.admin)
        self.assertIsNotNone(note.restored_at)

    def test_search_notes_case_insensitive_substring(self):
        StaffNoteService.create_note(self.course, author=self.staff, content="Waiting for original certificate")
        StaffNoteService.create_note(self.course, author=self.staff, content="Fee confirmation pending")
        results = StaffNoteService.search_notes(self.course, "CERTIFICATE")
        self.assertEqual(results.count(), 1)

    def test_notes_for_different_objects_are_independent(self):
        college2, course2 = _make_college_and_course(name="Other College", slug="other-college-notes-test")
        StaffNoteService.create_note(self.course, author=self.staff, content="On course A")
        self.assertEqual(StaffNoteService.get_notes(self.course).count(), 1)
        self.assertEqual(StaffNoteService.get_notes(course2).count(), 0)


class StaffNotePermissionsTests(TestCase):
    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.student = User.objects.create_user(username="student1", password="pass12345", role=User.Role.STUDENT)
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF)
        self.other_staff = User.objects.create_user(username="staff2", password="pass12345", role=User.Role.COLLEGE_STAFF)
        self.college_admin = User.objects.create_user(username="cadmin", password="pass12345", role=User.Role.COLLEGE_ADMIN)
        self.platform_admin = User.objects.create_user(
            username="padmin", password="pass12345", role=User.Role.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )

    def test_student_can_never_view_or_create_notes(self):
        self.assertFalse(can_view_notes(self.student))
        self.assertFalse(can_create_note(self.student))

    def test_staff_admin_platform_admin_can_view_and_create(self):
        for user in (self.staff, self.college_admin, self.platform_admin):
            self.assertTrue(can_view_notes(user))
            self.assertTrue(can_create_note(user))

    def test_staff_can_edit_and_delete_only_own_note(self):
        note = StaffNoteService.create_note(self.course, author=self.staff, content="Mine")
        self.assertTrue(can_edit_note(self.staff, note))
        self.assertTrue(can_delete_note(self.staff, note))
        self.assertFalse(can_edit_note(self.other_staff, note))
        self.assertFalse(can_delete_note(self.other_staff, note))

    def test_college_admin_has_full_access_to_any_note(self):
        note = StaffNoteService.create_note(self.course, author=self.staff, content="Staff's note")
        self.assertTrue(can_edit_note(self.college_admin, note))
        self.assertTrue(can_delete_note(self.college_admin, note))

    def test_platform_admin_has_full_access_to_any_note(self):
        note = StaffNoteService.create_note(self.course, author=self.staff, content="Staff's note")
        self.assertTrue(can_edit_note(self.platform_admin, note))
        self.assertTrue(can_delete_note(self.platform_admin, note))

    def test_only_admin_or_platform_admin_can_restore(self):
        """Feature 3: 'Restore Note (Administrator only)' -- explicitly
        not available to plain College Staff, even for their own note."""
        note = StaffNoteService.create_note(self.course, author=self.staff, content="Mine")
        StaffNoteService.delete_note(note, deleted_by=self.staff)
        self.assertFalse(can_restore_note(self.staff, note))
        self.assertTrue(can_restore_note(self.college_admin, note))
        self.assertTrue(can_restore_note(self.platform_admin, note))

    def test_cannot_restore_a_note_that_isnt_deleted(self):
        note = StaffNoteService.create_note(self.course, author=self.staff, content="Mine")
        self.assertFalse(can_restore_note(self.college_admin, note))

    def test_deleted_note_is_never_directly_editable(self):
        note = StaffNoteService.create_note(self.course, author=self.staff, content="Mine")
        StaffNoteService.delete_note(note, deleted_by=self.staff)
        self.assertFalse(can_edit_note(self.staff, note))
        self.assertFalse(can_edit_note(self.college_admin, note))
