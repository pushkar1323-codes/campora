from django.test import TestCase
from django.urls import reverse

from accounts.models import StaffProfile, User
from admissions.models import CorrectionRequest, Enquiry
from courses.models import College, Course


def _make_college_and_course(name="Test College", slug=None):
    college = College.objects.create(
        name=name, state="State", city="City", status=College.Status.APPROVED,
        **({"slug": slug} if slug else {}),
    )
    course = Course.objects.create(college=college, course_name="B.Tech CSE", duration="4 Years", eligibility="Class 12")
    return college, course


class EnquiryEditPersonalFieldLockoutTests(TestCase):
    """Phase 1, Feature 1/2/3/7: personal-information fields must never be
    editable by College Admin/College Staff -- not rendered, and not
    acceptable even via a hand-crafted POST body."""

    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF, is_staff=True)
        StaffProfile.objects.create(user=self.staff, college=self.college, designation="Staff")
        self.platform_admin = User.objects.create_user(
            username="padmin", password="pass12345", role=User.Role.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )
        self.enquiry = Enquiry.objects.create(
            full_name="Student One", father_name="F", email="s1@example.com", mobile="9999999999",
            address="Addr", dob="2000-01-01", gender="M", course=self.course,
            qualification="Class 12", percentage=80, admission_year=2026,
        )

    def test_staff_edit_form_excludes_personal_fields(self):
        self.client.login(username="staff1", password="pass12345")
        response = self.client.get(reverse("dashboard:enquiry_edit", args=[self.enquiry.pk]))
        self.assertNotContains(response, 'name="full_name"')
        self.assertNotContains(response, 'name="mobile"')
        self.assertNotContains(response, 'name="dob"')

    def test_staff_edit_form_excludes_academic_fields(self):
        """Bugfix regression: qualification/percentage were originally
        rendered in an always-visible "Academic Details" section outside
        the personal-field lockout, so College Staff could edit them
        despite Feature 1. They're self-reported student data, same
        ownership boundary as the identity fields above."""
        self.client.login(username="staff1", password="pass12345")
        response = self.client.get(reverse("dashboard:enquiry_edit", args=[self.enquiry.pk]))
        self.assertNotContains(response, 'name="qualification"')
        self.assertNotContains(response, 'name="percentage"')
        # admission_year is intentionally still staff-editable
        self.assertContains(response, 'name="admission_year"')

    def test_staff_post_cannot_change_personal_fields(self):
        self.client.login(username="staff1", password="pass12345")
        self.client.post(reverse("dashboard:enquiry_edit", args=[self.enquiry.pk]), {
            "college": self.college.pk, "course": self.course.pk, "status": Enquiry.Status.NEW,
            "qualification": "Class 12", "percentage": "80.00", "admission_year": "2026",
            "full_name": "HACKED", "email": "hacked@example.com", "mobile": "0000000000",
            "address": "hacked", "dob": "1999-01-01", "gender": "M", "father_name": "hacked",
        })
        self.enquiry.refresh_from_db()
        self.assertEqual(self.enquiry.full_name, "Student One")

    def test_staff_post_cannot_change_academic_fields(self):
        self.client.login(username="staff1", password="pass12345")
        self.client.post(reverse("dashboard:enquiry_edit", args=[self.enquiry.pk]), {
            "college": self.college.pk, "course": self.course.pk, "status": Enquiry.Status.NEW,
            "qualification": "HACKED QUALIFICATION", "percentage": "1.00", "admission_year": "2026",
        })
        self.enquiry.refresh_from_db()
        self.assertEqual(self.enquiry.qualification, "Class 12")
        self.assertEqual(float(self.enquiry.percentage), 80.0)

    def test_platform_admin_edit_form_includes_personal_fields(self):
        self.client.login(username="padmin", password="pass12345")
        response = self.client.get(reverse("dashboard:enquiry_edit", args=[self.enquiry.pk]))
        self.assertContains(response, 'name="full_name"')
        self.assertContains(response, 'name="qualification"')
        self.assertContains(response, 'name="percentage"')

    def test_platform_admin_can_change_personal_fields(self):
        self.client.login(username="padmin", password="pass12345")
        self.client.post(reverse("dashboard:enquiry_edit", args=[self.enquiry.pk]), {
            "college": self.college.pk, "course": self.course.pk, "status": Enquiry.Status.NEW,
            "qualification": "Class 12 (Updated)", "percentage": "91.00", "admission_year": "2026",
            "full_name": "Corrected Name", "email": "corrected@example.com", "mobile": "1111111111",
            "address": "Corrected addr", "dob": "1999-01-01", "gender": "M", "father_name": "Corrected Father",
        })
        self.enquiry.refresh_from_db()
        self.assertEqual(self.enquiry.full_name, "Corrected Name")
        self.assertEqual(self.enquiry.qualification, "Class 12 (Updated)")
        self.assertEqual(float(self.enquiry.percentage), 91.0)


class CorrectionRequestWorkflowTests(TestCase):
    """Phase 1, Feature 6/7: staff can request corrections and resolve
    them, scoped to their own college; corrections are never
    auto-approved."""

    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.other_college, self.other_course = _make_college_and_course(name="Other College", slug="other-college")
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF, is_staff=True)
        StaffProfile.objects.create(user=self.staff, college=self.college, designation="Staff")
        self.other_staff = User.objects.create_user(username="staff2", password="pass12345", role=User.Role.COLLEGE_STAFF, is_staff=True)
        StaffProfile.objects.create(user=self.other_staff, college=self.other_college, designation="Staff")
        self.enquiry = Enquiry.objects.create(
            full_name="Student One", father_name="F", email="s1@example.com", mobile="9999999999",
            address="Addr", dob="2000-01-01", gender="M", course=self.course,
            qualification="Class 12", percentage=80, admission_year=2026,
        )

    def test_staff_can_request_correction_on_own_college_enquiry(self):
        self.client.login(username="staff1", password="pass12345")
        response = self.client.post(
            reverse("dashboard:request_correction", args=[self.enquiry.pk]),
            {"reason": "Incorrect phone number", "message": "Please update."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.enquiry.correction_requests.count(), 1)
        self.assertEqual(self.enquiry.correction_requests.first().status, CorrectionRequest.Status.OPEN)

    def test_staff_cannot_request_correction_on_other_college_enquiry(self):
        self.client.login(username="staff2", password="pass12345")
        response = self.client.post(
            reverse("dashboard:request_correction", args=[self.enquiry.pk]),
            {"reason": "Incorrect phone number"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.enquiry.correction_requests.count(), 0)

    def test_resolve_correction_requires_staff_action_not_automatic(self):
        correction = CorrectionRequest.objects.create(enquiry=self.enquiry, requested_by=self.staff, reason="Fix phone")
        self.assertEqual(correction.status, CorrectionRequest.Status.OPEN)

        self.client.login(username="staff1", password="pass12345")
        response = self.client.post(
            reverse("dashboard:resolve_correction", args=[self.enquiry.pk, correction.pk])
        )
        self.assertEqual(response.status_code, 302)
        correction.refresh_from_db()
        self.assertEqual(correction.status, CorrectionRequest.Status.RESOLVED)
        self.assertEqual(correction.resolved_by, self.staff)


class EnquiryMessageReplyViewTests(TestCase):
    """Phase 2A: staff replies through the dashboard, scoped by the same
    college-ownership rules as every other staff enquiry action."""

    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.other_college, self.other_course = _make_college_and_course(name="Other College", slug="other-college-msg")
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF, is_staff=True)
        StaffProfile.objects.create(user=self.staff, college=self.college, designation="Staff")
        self.other_staff = User.objects.create_user(username="staff2", password="pass12345", role=User.Role.COLLEGE_STAFF, is_staff=True)
        StaffProfile.objects.create(user=self.other_staff, college=self.other_college, designation="Staff")
        self.enquiry = Enquiry.objects.create(
            full_name="Student One", father_name="F", email="s1@example.com", mobile="9999999999",
            address="Addr", dob="2000-01-01", gender="M", course=self.course,
            qualification="Class 12", percentage=80, admission_year=2026,
        )

    def test_staff_can_reply_on_own_college_enquiry(self):
        self.client.login(username="staff1", password="pass12345")
        response = self.client.post(
            reverse("dashboard:enquiry_message_reply", args=[self.enquiry.pk]), {"content": "Please upload your marksheet."}
        )
        self.assertEqual(response.status_code, 302)
        from communication.services import CommunicationService
        latest = CommunicationService.get_latest_message(self.enquiry)
        self.assertEqual(latest.content, "Please upload your marksheet.")
        self.assertEqual(latest.sender, self.staff)

    def test_staff_cannot_reply_on_other_college_enquiry(self):
        self.client.login(username="staff2", password="pass12345")
        response = self.client.post(
            reverse("dashboard:enquiry_message_reply", args=[self.enquiry.pk]), {"content": "Not allowed"}
        )
        self.assertEqual(response.status_code, 404)

    def test_enquiry_detail_marks_thread_read_for_staff(self):
        from communication.services import CommunicationService
        student = User.objects.create_user(username="student1", password="pass12345", role=User.Role.STUDENT)
        self.enquiry.submitted_by = student
        self.enquiry.save()
        CommunicationService.post_message(self.enquiry, sender=student, content="Hi")
        self.assertEqual(CommunicationService.get_unread_count(self.enquiry, self.staff), 1)

        self.client.login(username="staff1", password="pass12345")
        self.client.get(reverse("dashboard:enquiry_detail", args=[self.enquiry.pk]))
        self.assertEqual(CommunicationService.get_unread_count(self.enquiry, self.staff), 0)


class MessageEditDeleteViewTests(TestCase):
    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF, is_staff=True)
        StaffProfile.objects.create(user=self.staff, college=self.college, designation="Staff")
        self.other_staff = User.objects.create_user(username="staff2", password="pass12345", role=User.Role.COLLEGE_STAFF, is_staff=True)
        StaffProfile.objects.create(user=self.other_staff, college=self.college, designation="Staff")
        self.enquiry = Enquiry.objects.create(
            full_name="Student One", father_name="F", email="s1@example.com", mobile="9999999999",
            address="Addr", dob="2000-01-01", gender="M", course=self.course,
            qualification="Class 12", percentage=80, admission_year=2026,
        )
        from communication.services import CommunicationService
        self.message = CommunicationService.post_message(self.enquiry, sender=self.staff, content="Original")

    def test_sender_can_edit_own_message(self):
        self.client.login(username="staff1", password="pass12345")
        response = self.client.post(
            reverse("dashboard:message_edit", args=[self.message.pk]), {"content": "Updated"}
        )
        self.assertEqual(response.status_code, 302)
        self.message.refresh_from_db()
        self.assertEqual(self.message.content, "Updated")
        self.assertTrue(self.message.is_edited)

    def test_other_staff_cannot_edit_message(self):
        self.client.login(username="staff2", password="pass12345")
        response = self.client.get(reverse("dashboard:message_edit", args=[self.message.pk]))
        self.assertEqual(response.status_code, 404)

    def test_sender_can_delete_own_message(self):
        self.client.login(username="staff1", password="pass12345")
        response = self.client.post(reverse("dashboard:message_delete", args=[self.message.pk]))
        self.assertEqual(response.status_code, 302)
        self.message.refresh_from_db()
        self.assertTrue(self.message.is_deleted)
        self.assertEqual(self.message.deleted_by, self.staff)


class StaffNoteViewTests(TestCase):
    """Phase 2B: Internal Staff Notes -- view-level enforcement of the
    Feature 4 role matrix and Feature 10 college isolation, plus Feature 9
    (Students must never be able to reach any of this)."""

    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.other_college, self.other_course = _make_college_and_course(name="Other College", slug="other-college-notes")
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF, is_staff=True)
        StaffProfile.objects.create(user=self.staff, college=self.college, designation="Staff")
        self.other_staff = User.objects.create_user(username="staff2", password="pass12345", role=User.Role.COLLEGE_STAFF, is_staff=True)
        StaffProfile.objects.create(user=self.other_staff, college=self.college, designation="Staff")
        self.college_admin = User.objects.create_user(username="cadmin", password="pass12345", role=User.Role.COLLEGE_ADMIN, is_staff=True)
        StaffProfile.objects.create(user=self.college_admin, college=self.college, designation="Admin")
        self.other_college_staff = User.objects.create_user(username="staff3", password="pass12345", role=User.Role.COLLEGE_STAFF, is_staff=True)
        StaffProfile.objects.create(user=self.other_college_staff, college=self.other_college, designation="Staff")
        self.student = User.objects.create_user(username="student1", password="pass12345", role=User.Role.STUDENT)
        self.enquiry = Enquiry.objects.create(
            full_name="Student One", father_name="F", email="s1@example.com", mobile="9999999999",
            address="Addr", dob="2000-01-01", gender="M", course=self.course,
            qualification="Class 12", percentage=80, admission_year=2026,
        )

    def test_staff_can_create_note_on_own_college_enquiry(self):
        self.client.login(username="staff1", password="pass12345")
        response = self.client.post(
            reverse("dashboard:note_create", args=[self.enquiry.pk]), {"content": "Waiting for certificate."}
        )
        self.assertEqual(response.status_code, 302)
        from staff_notes.services import StaffNoteService
        self.assertEqual(StaffNoteService.get_notes(self.enquiry).count(), 1)

    def test_staff_cannot_create_note_on_other_college_enquiry(self):
        self.client.login(username="staff3", password="pass12345")
        response = self.client.post(
            reverse("dashboard:note_create", args=[self.enquiry.pk]), {"content": "Not allowed"}
        )
        self.assertEqual(response.status_code, 404)

    def test_enquiry_detail_never_reachable_by_student(self):
        """Feature 9: the entire page Staff Notes lives on must be
        unreachable by a Student, not merely hidden within it."""
        self.client.login(username="student1", password="pass12345")
        response = self.client.get(reverse("dashboard:enquiry_detail", args=[self.enquiry.pk]))
        self.assertEqual(response.status_code, 403)

    def test_staff_notes_never_appear_in_student_conversation_page(self):
        """Belt-and-suspenders: even though Students can't reach
        dashboard:enquiry_detail at all, also confirm note content never
        leaks into the student-facing conversation page."""
        from staff_notes.services import StaffNoteService
        StaffNoteService.create_note(self.enquiry, author=self.staff, content="SECRET_STAFF_ONLY_NOTE_TEXT")
        self.enquiry.submitted_by = self.student
        self.enquiry.save()
        self.client.login(username="student1", password="pass12345")
        response = self.client.get(reverse("admissions:enquiry_conversation", args=[self.enquiry.pk]))
        self.assertNotContains(response, "SECRET_STAFF_ONLY_NOTE_TEXT")

    def test_staff_can_edit_own_note_but_not_colleagues_note(self):
        from staff_notes.services import StaffNoteService
        note = StaffNoteService.create_note(self.enquiry, author=self.staff, content="Original")

        self.client.login(username="staff1", password="pass12345")
        response = self.client.post(reverse("dashboard:note_edit", args=[note.pk]), {"content": "Updated"})
        self.assertEqual(response.status_code, 302)
        note.refresh_from_db()
        self.assertEqual(note.content, "Updated")
        self.client.logout()

        self.client.login(username="staff2", password="pass12345")
        response = self.client.get(reverse("dashboard:note_edit", args=[note.pk]))
        self.assertEqual(response.status_code, 404)

    def test_college_admin_can_edit_and_delete_staffs_note(self):
        from staff_notes.services import StaffNoteService
        note = StaffNoteService.create_note(self.enquiry, author=self.staff, content="Staff's note")

        self.client.login(username="cadmin", password="pass12345")
        response = self.client.post(reverse("dashboard:note_edit", args=[note.pk]), {"content": "Admin corrected it"})
        self.assertEqual(response.status_code, 302)
        note.refresh_from_db()
        self.assertEqual(note.content, "Admin corrected it")

        response = self.client.post(reverse("dashboard:note_delete", args=[note.pk]))
        self.assertEqual(response.status_code, 302)
        note.refresh_from_db()
        self.assertTrue(note.is_deleted)

    def test_plain_staff_cannot_restore_even_own_note(self):
        from staff_notes.services import StaffNoteService
        note = StaffNoteService.create_note(self.enquiry, author=self.staff, content="Mine")
        StaffNoteService.delete_note(note, deleted_by=self.staff)

        self.client.login(username="staff1", password="pass12345")
        response = self.client.post(reverse("dashboard:note_restore", args=[note.pk]))
        self.assertEqual(response.status_code, 404)
        note.refresh_from_db()
        self.assertTrue(note.is_deleted)

    def test_college_admin_can_restore_note(self):
        from staff_notes.services import StaffNoteService
        note = StaffNoteService.create_note(self.enquiry, author=self.staff, content="Mine")
        StaffNoteService.delete_note(note, deleted_by=self.staff)

        self.client.login(username="cadmin", password="pass12345")
        response = self.client.post(reverse("dashboard:note_restore", args=[note.pk]))
        self.assertEqual(response.status_code, 302)
        note.refresh_from_db()
        self.assertFalse(note.is_deleted)
        self.assertEqual(note.restored_by, self.college_admin)

    def test_deleted_note_hidden_from_plain_staff_but_visible_to_admin_for_restore(self):
        from staff_notes.services import StaffNoteService
        note = StaffNoteService.create_note(self.enquiry, author=self.staff, content="Deleted note text")
        StaffNoteService.delete_note(note, deleted_by=self.staff)

        self.client.login(username="staff1", password="pass12345")
        response = self.client.get(reverse("dashboard:enquiry_detail", args=[self.enquiry.pk]))
        self.assertNotContains(response, "Deleted note text")
        self.client.logout()

        self.client.login(username="cadmin", password="pass12345")
        response = self.client.get(reverse("dashboard:enquiry_detail", args=[self.enquiry.pk]))
        self.assertContains(response, "Deleted note text")


class UnreadMessageBadgeTests(TestCase):
    """Phase 2B, Feature 6/8: unread badges shown on list views (not the
    already-marked-read detail page), computed without N+1 queries."""

    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF, is_staff=True)
        StaffProfile.objects.create(user=self.staff, college=self.college, designation="Staff")
        self.student = User.objects.create_user(username="student1", password="pass12345", role=User.Role.STUDENT)
        self.enquiry = Enquiry.objects.create(
            full_name="Student One", father_name="F", email="s1@example.com", mobile="9999999999",
            address="Addr", dob="2000-01-01", gender="M", course=self.course,
            qualification="Class 12", percentage=80, admission_year=2026, submitted_by=self.student,
        )

    def test_bulk_unread_counts_matches_individual_calls(self):
        from communication.services import CommunicationService
        CommunicationService.post_message(self.enquiry, sender=self.student, content="Hi")
        bulk = CommunicationService.get_unread_counts_bulk(Enquiry, [self.enquiry.pk], self.staff)
        individual = CommunicationService.get_unread_count(self.enquiry, self.staff)
        self.assertEqual(bulk.get(self.enquiry.pk, 0), individual)
        self.assertEqual(bulk[self.enquiry.pk], 1)

    def test_enquiry_list_shows_unread_badge_before_opening_detail(self):
        from communication.services import CommunicationService
        CommunicationService.post_message(self.enquiry, sender=self.student, content="Hi")

        self.client.login(username="staff1", password="pass12345")
        response = self.client.get(reverse("dashboard:enquiry_list"))
        self.assertContains(response, "1")  # unread badge rendered

        # Opening the detail page marks it read; list should then show none.
        self.client.get(reverse("dashboard:enquiry_detail", args=[self.enquiry.pk]))
        response = self.client.get(reverse("dashboard:enquiry_list"))
        self.assertEqual(
            CommunicationService.get_unread_count(self.enquiry, self.staff), 0
        )


class TimelineStaffEventTests(TestCase):
    """Phase 3A: automatic Timeline events fire from staff-side actions."""

    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF, is_staff=True)
        StaffProfile.objects.create(user=self.staff, college=self.college, designation="Staff")
        self.enquiry = Enquiry.objects.create(
            full_name="Student One", father_name="F", email="s1@example.com", mobile="9999999999",
            address="Addr", dob="2000-01-01", gender="M", course=self.course,
            qualification="Class 12", percentage=80, admission_year=2026, status=Enquiry.Status.NEW,
        )

    def test_staff_reply_logs_timeline_event(self):
        from timeline.services import TimelineService
        self.client.login(username="staff1", password="pass12345")
        self.client.post(reverse("dashboard:enquiry_message_reply", args=[self.enquiry.pk]), {"content": "Please upload documents."})
        entries = list(TimelineService.get_timeline(self.enquiry))
        self.assertTrue(any(e.event_type == "STAFF_REPLIED" for e in entries))

    def test_status_change_logs_generic_status_updated_event(self):
        from timeline.services import TimelineService
        self.client.login(username="staff1", password="pass12345")
        self.client.post(reverse("dashboard:enquiry_edit", args=[self.enquiry.pk]), {
            "college": self.college.pk, "course": self.course.pk, "status": Enquiry.Status.CONTACTED,
            "admission_year": "2026",
        })
        entries = list(TimelineService.get_timeline(self.enquiry))
        matching = [e for e in entries if e.event_type == "STATUS_UPDATED"]
        self.assertEqual(len(matching), 1)
        self.assertIn("New", matching[0].description)
        self.assertIn("Contacted", matching[0].description)

    def test_status_change_to_admitted_logs_specific_event(self):
        from timeline.services import TimelineService
        self.client.login(username="staff1", password="pass12345")
        self.client.post(reverse("dashboard:enquiry_edit", args=[self.enquiry.pk]), {
            "college": self.college.pk, "course": self.course.pk, "status": Enquiry.Status.ADMITTED,
            "admission_year": "2026",
        })
        entries = list(TimelineService.get_timeline(self.enquiry))
        self.assertTrue(any(e.event_type == "ENQUIRY_ADMITTED" and e.title == "Enquiry Admitted" for e in entries))

    def test_status_change_to_rejected_logs_specific_event(self):
        from timeline.services import TimelineService
        self.client.login(username="staff1", password="pass12345")
        self.client.post(reverse("dashboard:enquiry_edit", args=[self.enquiry.pk]), {
            "college": self.college.pk, "course": self.course.pk, "status": Enquiry.Status.REJECTED,
            "admission_year": "2026",
        })
        entries = list(TimelineService.get_timeline(self.enquiry))
        self.assertTrue(any(e.event_type == "ENQUIRY_REJECTED" and e.title == "Enquiry Rejected" for e in entries))

    def test_no_status_change_logs_no_event(self):
        """Saving the edit form without actually changing the status
        must not fabricate a spurious 'Status Updated' entry."""
        from timeline.services import TimelineService
        self.client.login(username="staff1", password="pass12345")
        self.client.post(reverse("dashboard:enquiry_edit", args=[self.enquiry.pk]), {
            "college": self.college.pk, "course": self.course.pk, "status": Enquiry.Status.NEW,
            "admission_year": "2026",
        })
        entries = list(TimelineService.get_timeline(self.enquiry))
        self.assertEqual(len(entries), 0)

    def test_correction_resolution_logs_timeline_event(self):
        from timeline.services import TimelineService
        from admissions.services import create_correction_request

        correction = create_correction_request(self.enquiry, requested_by=self.staff, reason="Fix phone")
        self.client.login(username="staff1", password="pass12345")
        self.client.post(reverse("dashboard:resolve_correction", args=[self.enquiry.pk, correction.pk]))
        entries = list(TimelineService.get_timeline(self.enquiry))
        self.assertTrue(any(e.event_type == "CORRECTION_RESOLVED" for e in entries))

    def test_enquiry_detail_renders_timeline_entries(self):
        from timeline.services import TimelineService
        TimelineService.log_event(self.enquiry, category="STATUS", event_type="TEST", title="Test Timeline Entry")
        self.client.login(username="staff1", password="pass12345")
        response = self.client.get(reverse("dashboard:enquiry_detail", args=[self.enquiry.pk]))
        self.assertContains(response, "Test Timeline Entry")
