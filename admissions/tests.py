from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import StudentProfile, User
from courses.models import College, Course

from .models import CorrectionRequest, Enquiry
from .services import (
    can_staff_edit_personal_fields,
    can_student_edit_enquiry,
    correction_extends_edit_window,
    create_correction_request,
    get_active_correction_request,
    is_within_edit_window,
    mark_correction_responded,
    resolve_correction_request,
)


def _make_college_and_course():
    college = College.objects.create(name="Test College", state="State", city="City", status=College.Status.APPROVED)
    course = Course.objects.create(college=college, course_name="B.Tech CSE", duration="4 Years", eligibility="Class 12")
    return college, course


class CorrectionRequestModelTests(TestCase):
    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.student = User.objects.create_user(username="student1", password="pass12345", role=User.Role.STUDENT)
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF)
        self.enquiry = Enquiry.objects.create(
            full_name="Student One", father_name="F", email="s1@example.com", mobile="9999999999",
            address="Addr", dob="2000-01-01", gender="M", course=self.course,
            qualification="Class 12", percentage=80, admission_year=2026, submitted_by=self.student,
        )

    def test_is_open_true_for_open_and_responded(self):
        correction = CorrectionRequest.objects.create(enquiry=self.enquiry, requested_by=self.staff, reason="Fix phone")
        self.assertTrue(correction.is_open)
        correction.status = CorrectionRequest.Status.RESPONDED
        correction.save()
        self.assertTrue(correction.is_open)

    def test_is_open_false_once_resolved(self):
        correction = CorrectionRequest.objects.create(
            enquiry=self.enquiry, requested_by=self.staff, reason="Fix phone", status=CorrectionRequest.Status.RESOLVED,
        )
        self.assertFalse(correction.is_open)


class AdmissionServicesTests(TestCase):
    """Phase 1 business rules -- admissions/services.py. Kept independent
    of HTTP/views per the "reusable service/helper" requirement, so these
    rules are tested directly rather than only indirectly through views."""

    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.student = User.objects.create_user(username="student1", password="pass12345", role=User.Role.STUDENT)
        self.other_student = User.objects.create_user(username="student2", password="pass12345", role=User.Role.STUDENT)
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF)
        self.platform_admin = User.objects.create_user(
            username="padmin", password="pass12345", role=User.Role.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )
        self.enquiry = Enquiry.objects.create(
            full_name="Student One", father_name="F", email="s1@example.com", mobile="9999999999",
            address="Addr", dob="2000-01-01", gender="M", course=self.course,
            qualification="Class 12", percentage=80, admission_year=2026, submitted_by=self.student,
        )

    def test_fresh_enquiry_within_edit_window(self):
        self.assertTrue(is_within_edit_window(self.enquiry))
        self.assertTrue(can_student_edit_enquiry(self.enquiry, self.student))

    def test_owner_only_can_edit(self):
        self.assertFalse(can_student_edit_enquiry(self.enquiry, self.other_student))

    def test_edit_window_expiry_blocks_edit(self):
        Enquiry.objects.filter(pk=self.enquiry.pk).update(created_at=timezone.now() - timedelta(minutes=31))
        self.enquiry.refresh_from_db()
        self.assertFalse(is_within_edit_window(self.enquiry))
        self.assertFalse(can_student_edit_enquiry(self.enquiry, self.student))

    def test_open_correction_extends_expired_window(self):
        Enquiry.objects.filter(pk=self.enquiry.pk).update(created_at=timezone.now() - timedelta(minutes=31))
        self.enquiry.refresh_from_db()
        create_correction_request(self.enquiry, requested_by=self.staff, reason="Fix phone")
        self.assertTrue(can_student_edit_enquiry(self.enquiry, self.student))

    def test_correction_extension_is_configurable(self):
        """CORRECTION_REQUEST_EXTENDS_EDIT_WINDOW=False must remove the
        override entirely -- this is what makes it a configurable business
        rule rather than a hard-coded exception."""
        Enquiry.objects.filter(pk=self.enquiry.pk).update(created_at=timezone.now() - timedelta(minutes=31))
        self.enquiry.refresh_from_db()
        create_correction_request(self.enquiry, requested_by=self.staff, reason="Fix phone")
        with self.settings(CORRECTION_REQUEST_EXTENDS_EDIT_WINDOW=False):
            self.assertFalse(correction_extends_edit_window())
            self.assertFalse(can_student_edit_enquiry(self.enquiry, self.student))

    def test_resolved_correction_does_not_extend_window(self):
        Enquiry.objects.filter(pk=self.enquiry.pk).update(created_at=timezone.now() - timedelta(minutes=31))
        self.enquiry.refresh_from_db()
        correction = create_correction_request(self.enquiry, requested_by=self.staff, reason="Fix phone")
        resolve_correction_request(correction, resolved_by=self.staff)
        self.assertIsNone(get_active_correction_request(self.enquiry))
        self.assertFalse(can_student_edit_enquiry(self.enquiry, self.student))

    def test_mark_correction_responded_never_auto_resolves(self):
        correction = create_correction_request(self.enquiry, requested_by=self.staff, reason="Fix phone")
        mark_correction_responded(correction)
        correction.refresh_from_db()
        self.assertEqual(correction.status, CorrectionRequest.Status.RESPONDED)
        self.assertNotEqual(correction.status, CorrectionRequest.Status.RESOLVED)

    def test_only_platform_admin_can_edit_personal_fields(self):
        self.assertTrue(can_staff_edit_personal_fields(self.platform_admin))
        self.assertFalse(can_staff_edit_personal_fields(self.staff))

    def test_edit_window_minutes_is_configurable(self):
        with self.settings(ENQUIRY_EDIT_WINDOW_MINUTES=1):
            Enquiry.objects.filter(pk=self.enquiry.pk).update(created_at=timezone.now() - timedelta(minutes=2))
            self.enquiry.refresh_from_db()
            self.assertFalse(is_within_edit_window(self.enquiry))


class EnquirySelfEditViewTests(TestCase):
    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.student = User.objects.create_user(
            username="student1", password="pass12345", role=User.Role.STUDENT, email="s1@example.com"
        )
        StudentProfile.objects.create(user=self.student, phone="9999999999")
        self.other_student = User.objects.create_user(username="student2", password="pass12345", role=User.Role.STUDENT)
        self.enquiry = Enquiry.objects.create(
            full_name="Student One", father_name="F", email="s1@example.com", mobile="9999999999",
            address="Addr", dob="2000-01-01", gender="M", course=self.course,
            qualification="Class 12", percentage=80, admission_year=2026, submitted_by=self.student,
        )

    def test_owner_can_edit_within_window(self):
        self.client.login(username="student1", password="pass12345")
        response = self.client.post(
            reverse("admissions:enquiry_self_edit", args=[self.enquiry.pk]),
            {"course": self.course.pk, "qualification": "Updated", "percentage": "91.00", "admission_year": "2026"},
        )
        self.assertEqual(response.status_code, 302)
        self.enquiry.refresh_from_db()
        self.assertEqual(self.enquiry.qualification, "Updated")

    def test_non_owner_gets_404(self):
        self.client.login(username="student2", password="pass12345")
        response = self.client.get(reverse("admissions:enquiry_self_edit", args=[self.enquiry.pk]))
        self.assertEqual(response.status_code, 404)

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(reverse("admissions:enquiry_self_edit", args=[self.enquiry.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_expired_window_shows_locked_message_and_blocks_post(self):
        Enquiry.objects.filter(pk=self.enquiry.pk).update(created_at=timezone.now() - timedelta(minutes=31))
        self.client.login(username="student1", password="pass12345")
        response = self.client.get(reverse("admissions:enquiry_self_edit", args=[self.enquiry.pk]))
        self.assertContains(response, "Editing is no longer available")

        response = self.client.post(
            reverse("admissions:enquiry_self_edit", args=[self.enquiry.pk]),
            {"course": self.course.pk, "qualification": "HACKED", "percentage": "1", "admission_year": "2026"},
        )
        self.enquiry.refresh_from_db()
        self.assertNotEqual(self.enquiry.qualification, "HACKED")


class EnquiryCreateRegressionTests(TestCase):
    """Guards that Phase 1 didn't break anonymous/guest enquiry submission."""

    def setUp(self):
        self.college, self.course = _make_college_and_course()

    def test_anonymous_enquiry_submission_still_works(self):
        response = self.client.post(
            reverse("admissions:enquiry_create", args=[self.course.pk]),
            {
                "full_name": "Anon Student", "father_name": "Anon Father", "email": "anon@example.com",
                "mobile": "6666666666", "address": "Addr", "dob": "2002-01-01", "gender": "M",
                "qualification": "Class 12", "percentage": "88.00", "admission_year": "2026",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Enquiry.objects.filter(email="anon@example.com", submitted_by__isnull=True).exists())


class EnquiryConversationViewTests(TestCase):
    """Phase 2A: student-facing conversation view, ownership + generic
    thread-permission enforcement, and the CorrectionRequest -> system
    message integration."""

    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.student = User.objects.create_user(
            username="student1", password="pass12345", role=User.Role.STUDENT, email="s1@example.com"
        )
        StudentProfile.objects.create(user=self.student, phone="9999999999")
        self.other_student = User.objects.create_user(username="student2", password="pass12345", role=User.Role.STUDENT)
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF)
        self.enquiry = Enquiry.objects.create(
            full_name="Student One", father_name="F", email="s1@example.com", mobile="9999999999",
            address="Addr", dob="2000-01-01", gender="M", course=self.course,
            qualification="Class 12", percentage=80, admission_year=2026, submitted_by=self.student,
        )

    def test_owner_can_view_conversation(self):
        self.client.login(username="student1", password="pass12345")
        response = self.client.get(reverse("admissions:enquiry_conversation", args=[self.enquiry.pk]))
        self.assertEqual(response.status_code, 200)

    def test_non_owner_gets_404(self):
        self.client.login(username="student2", password="pass12345")
        response = self.client.get(reverse("admissions:enquiry_conversation", args=[self.enquiry.pk]))
        self.assertEqual(response.status_code, 404)

    def test_student_can_send_message(self):
        self.client.login(username="student1", password="pass12345")
        response = self.client.post(
            reverse("admissions:enquiry_conversation", args=[self.enquiry.pk]), {"content": "Hello staff"}
        )
        self.assertEqual(response.status_code, 302)
        from communication.services import CommunicationService
        latest = CommunicationService.get_latest_message(self.enquiry)
        self.assertEqual(latest.content, "Hello staff")
        self.assertEqual(latest.sender, self.student)

    def test_correction_request_posts_system_message(self):
        from admissions.services import create_correction_request
        from communication.services import CommunicationService

        create_correction_request(self.enquiry, requested_by=self.staff, reason="Incorrect phone number")
        latest = CommunicationService.get_latest_message(self.enquiry)
        self.assertIsNotNone(latest)
        self.assertTrue(latest.is_system_generated)
        self.assertIn("Incorrect phone number", latest.content)
        self.assertIsNone(latest.sender)
