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

    def test_platform_admin_edit_form_includes_personal_fields(self):
        self.client.login(username="padmin", password="pass12345")
        response = self.client.get(reverse("dashboard:enquiry_edit", args=[self.enquiry.pk]))
        self.assertContains(response, 'name="full_name"')

    def test_platform_admin_can_change_personal_fields(self):
        self.client.login(username="padmin", password="pass12345")
        self.client.post(reverse("dashboard:enquiry_edit", args=[self.enquiry.pk]), {
            "college": self.college.pk, "course": self.course.pk, "status": Enquiry.Status.NEW,
            "qualification": "Class 12", "percentage": "80.00", "admission_year": "2026",
            "full_name": "Corrected Name", "email": "corrected@example.com", "mobile": "1111111111",
            "address": "Corrected addr", "dob": "1999-01-01", "gender": "M", "father_name": "Corrected Father",
        })
        self.enquiry.refresh_from_db()
        self.assertEqual(self.enquiry.full_name, "Corrected Name")


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
