from accounts.models import User
from courses.models import College, Course
from django.test import TestCase

from .models import AuditLog
from .permissions import can_view_audit_logs
from .services import AuditService


def _make_college_and_course(name="Test College", slug=None):
    college = College.objects.create(
        name=name, state="State", city="City", status=College.Status.APPROVED,
        **({"slug": slug} if slug else {}),
    )
    course = Course.objects.create(college=college, course_name="B.Tech CSE", duration="4 Years", eligibility="Class 12")
    return college, course


class AuditServiceTests(TestCase):
    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.admin = User.objects.create_user(username="cadmin", password="pass12345", role=User.Role.COLLEGE_ADMIN)

    def test_log_creates_entry(self):
        entry = AuditService.log(
            action="TEST_ACTION", category="System", severity=AuditLog.Severity.INFO,
            actor=self.admin, college=self.college,
        )
        self.assertEqual(entry.action, "TEST_ACTION")
        self.assertEqual(entry.actor, self.admin)

    def test_log_for_object_derives_target_fields(self):
        entry = AuditService.log_for_object(
            self.course, action="COURSE_TEST", category="Course Management", actor=self.admin,
        )
        self.assertEqual(entry.target_model, "courses.course")
        self.assertEqual(entry.object_id, str(self.course.pk))
        self.assertEqual(entry.object_display_name, str(self.course))

    def test_get_logs_for_object_matches_log_for_object_convention(self):
        AuditService.log_for_object(self.course, action="A", category="System")
        AuditService.log_for_object(self.college, action="B", category="System")
        course_logs = AuditService.get_logs_for_object(self.course)
        self.assertEqual(course_logs.count(), 1)
        self.assertEqual(course_logs.first().action, "A")

    def test_get_logs_for_college(self):
        college2, _ = _make_college_and_course(name="Other College", slug="other-college-audit-test")
        AuditService.log(action="A", college=self.college)
        AuditService.log(action="B", college=college2)
        self.assertEqual(AuditService.get_logs_for_college(self.college).count(), 1)

    def test_request_supplies_ip_and_user_agent(self):
        from django.test import RequestFactory
        rf = RequestFactory()
        request = rf.get("/", HTTP_USER_AGENT="TestBrowser/1.0")
        request.META["REMOTE_ADDR"] = "203.0.113.5"
        entry = AuditService.log(action="TEST", request=request)
        self.assertEqual(entry.ip_address, "203.0.113.5")
        self.assertEqual(entry.user_agent, "TestBrowser/1.0")

    def test_x_forwarded_for_preferred_over_remote_addr(self):
        from django.test import RequestFactory
        rf = RequestFactory()
        request = rf.get("/", HTTP_X_FORWARDED_FOR="198.51.100.7, 10.0.0.1")
        request.META["REMOTE_ADDR"] = "10.0.0.1"
        entry = AuditService.log(action="TEST", request=request)
        self.assertEqual(entry.ip_address, "198.51.100.7")


class AuditLogImmutabilityTests(TestCase):
    """Feature 5: immutable at every layer -- instance save(), instance
    delete(), and queryset-level update()/delete()."""

    def setUp(self):
        self.entry = AuditService.log(action="TEST_ACTION", category="System")

    def test_instance_save_after_creation_raises(self):
        self.entry.action = "MODIFIED"
        with self.assertRaises(ValueError):
            self.entry.save()

    def test_instance_delete_raises(self):
        with self.assertRaises(ValueError):
            self.entry.delete()

    def test_queryset_update_raises(self):
        with self.assertRaises(ValueError):
            AuditLog.objects.filter(pk=self.entry.pk).update(action="HACKED")

    def test_queryset_delete_raises(self):
        with self.assertRaises(ValueError):
            AuditLog.objects.filter(pk=self.entry.pk).delete()

    def test_record_survives_all_mutation_attempts(self):
        for attempt in [
            lambda: setattr(self.entry, "action", "x") or self.entry.save(),
            lambda: self.entry.delete(),
            lambda: AuditLog.objects.filter(pk=self.entry.pk).update(action="x"),
            lambda: AuditLog.objects.filter(pk=self.entry.pk).delete(),
        ]:
            try:
                attempt()
            except ValueError:
                pass
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.action, "TEST_ACTION")


class AuditPermissionsTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username="student1", password="pass12345", role=User.Role.STUDENT)
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF)
        self.college_admin = User.objects.create_user(username="cadmin", password="pass12345", role=User.Role.COLLEGE_ADMIN)
        self.platform_admin = User.objects.create_user(
            username="padmin", password="pass12345", role=User.Role.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )

    def test_student_never_can_view_audit_logs(self):
        self.assertFalse(can_view_audit_logs(self.student))

    def test_college_staff_cannot_view_audit_logs(self):
        """Feature 9: deliberately stricter than Timeline/Communication --
        College Staff is NOT among the authorized roles."""
        self.assertFalse(can_view_audit_logs(self.staff))

    def test_college_admin_can_view_audit_logs(self):
        self.assertTrue(can_view_audit_logs(self.college_admin))

    def test_platform_admin_can_view_audit_logs(self):
        self.assertTrue(can_view_audit_logs(self.platform_admin))


class AuthenticationAuditSignalTests(TestCase):
    """Feature 2 (Authentication category) via Django's own built-in auth
    signals -- covers CamporaLoginView/LogoutView with zero code changes
    at those call sites."""

    def setUp(self):
        self.user = User.objects.create_user(username="student1", password="pass12345", role=User.Role.STUDENT)

    def test_successful_login_logs_audit_entry(self):
        self.client.login(username="student1", password="pass12345")
        entry = AuditLog.objects.filter(action="USER_LOGIN", actor=self.user).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.action_category, "Authentication")

    def test_logout_logs_audit_entry(self):
        self.client.login(username="student1", password="pass12345")
        self.client.logout()
        self.assertTrue(AuditLog.objects.filter(action="USER_LOGOUT", actor=self.user).exists())

    def test_failed_login_logs_warning_entry(self):
        self.client.post("/accounts/login/", {"username": "student1", "password": "wrong-password"})
        entry = AuditLog.objects.filter(action="USER_LOGIN_FAILED").first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.severity, AuditLog.Severity.WARNING)
        self.assertIsNone(entry.actor)
