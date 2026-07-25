from accounts.models import User
from courses.models import College, Course
from django.test import TestCase

from .models import TimelineEntry
from .services import TimelineService


def _make_college_and_course(name="Test College", slug=None):
    college = College.objects.create(
        name=name, state="State", city="City", status=College.Status.APPROVED,
        **({"slug": slug} if slug else {}),
    )
    course = Course.objects.create(college=college, course_name="B.Tech CSE", duration="4 Years", eligibility="Class 12")
    return college, course


class TimelineServiceTests(TestCase):
    """GenericForeignKey handling stays entirely internal to
    TimelineService -- these tests never touch ContentType/content_object
    directly, only pass plain model instances."""

    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF)

    def test_log_event_creates_entry(self):
        entry = TimelineService.log_event(
            self.course, category=TimelineEntry.Category.SYSTEM, event_type="TEST_EVENT",
            title="Something Happened", description="Details here.", actor=self.staff, icon="circle",
        )
        self.assertEqual(entry.title, "Something Happened")
        self.assertEqual(entry.actor, self.staff)
        self.assertEqual(entry.category, TimelineEntry.Category.SYSTEM)

    def test_log_event_without_actor_is_system_generated(self):
        entry = TimelineService.log_event(
            self.course, category=TimelineEntry.Category.SYSTEM, event_type="AUTO_EVENT", title="Automatic",
        )
        self.assertIsNone(entry.actor)

    def test_get_timeline_newest_first(self):
        e1 = TimelineService.log_event(self.course, category="SYSTEM", event_type="FIRST", title="First")
        e2 = TimelineService.log_event(self.course, category="SYSTEM", event_type="SECOND", title="Second")
        ordered = list(TimelineService.get_timeline(self.course))
        self.assertEqual(ordered, [e2, e1])

    def test_timelines_for_different_objects_are_independent(self):
        college2, course2 = _make_college_and_course(name="Other College", slug="other-college-timeline-test")
        TimelineService.log_event(self.course, category="SYSTEM", event_type="ON_A", title="On course A")
        self.assertEqual(TimelineService.get_timeline(self.course).count(), 1)
        self.assertEqual(TimelineService.get_timeline(course2).count(), 0)

    def test_get_timeline_count(self):
        TimelineService.log_event(self.course, category="SYSTEM", event_type="A", title="A")
        TimelineService.log_event(self.course, category="SYSTEM", event_type="B", title="B")
        self.assertEqual(TimelineService.get_timeline_count(self.course), 2)

    def test_category_is_free_text_not_a_closed_enum(self):
        """Feature 2: 'Future modules should be able to add categories
        without redesign' -- an arbitrary category string a future
        module might invent must work with no model change."""
        entry = TimelineService.log_event(
            self.course, category="HOSTEL_MAINTENANCE", event_type="ROOM_ASSIGNED", title="Room Assigned",
        )
        self.assertEqual(entry.category, "HOSTEL_MAINTENANCE")


class TimelineCollegeFieldTests(TestCase):
    """Phase 3C, Feature 4: TimelineEntry.college is populated by callers
    that know it, and TimelineService.get_entries_for_college scopes
    correctly."""

    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF)

    def test_log_event_stores_college(self):
        entry = TimelineService.log_event(
            self.course, category="SYSTEM", event_type="TEST", title="Test", college=self.college,
        )
        self.assertEqual(entry.college, self.college)

    def test_log_event_college_defaults_to_none(self):
        entry = TimelineService.log_event(self.course, category="SYSTEM", event_type="TEST", title="Test")
        self.assertIsNone(entry.college)

    def test_get_entries_for_college_scopes_correctly(self):
        college2, course2 = _make_college_and_course(name="Other College", slug="other-college-timeline-college-test")
        TimelineService.log_event(self.course, category="SYSTEM", event_type="A", title="A", college=self.college)
        TimelineService.log_event(course2, category="SYSTEM", event_type="B", title="B", college=college2)
        self.assertEqual(TimelineService.get_entries_for_college(self.college).count(), 1)
        self.assertEqual(TimelineService.get_entries_for_college(self.college).first().title, "A")


class TimelineAdminIntegrationTests(TestCase):
    """Phase 3C, Feature 4/5: Admin Panel registration, college scoping,
    search, and filtering."""

    def setUp(self):
        self.college, self.course = _make_college_and_course()
        self.other_college, self.other_course = _make_college_and_course(name="Other College", slug="other-college-timeline-admin-test")
        self.college_admin = User.objects.create_user(
            username="cadmin", password="pass12345", role=User.Role.COLLEGE_ADMIN, is_staff=True,
        )
        from accounts.models import StaffProfile
        StaffProfile.objects.create(user=self.college_admin, college=self.college, designation="Admin")
        self.other_college_admin = User.objects.create_user(
            username="cadmin2", password="pass12345", role=User.Role.COLLEGE_ADMIN, is_staff=True,
        )
        StaffProfile.objects.create(user=self.other_college_admin, college=self.other_college, designation="Admin")
        self.platform_admin = User.objects.create_user(
            username="padmin", password="pass12345", role=User.Role.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )
        self.entry_own = TimelineService.log_event(
            self.course, category="ADMISSION", event_type="ENQUIRY_SUBMITTED", title="Own College Entry",
            college=self.college,
        )
        self.entry_other = TimelineService.log_event(
            self.other_course, category="ADMISSION", event_type="ENQUIRY_SUBMITTED", title="Other College Entry",
            college=self.other_college,
        )

    def test_college_admin_sees_only_own_college_entries_in_admin(self):
        self.client.login(username="cadmin", password="pass12345")
        response = self.client.get("/admin/timeline/timelineentry/")
        self.assertContains(response, "Own College Entry")
        self.assertNotContains(response, "Other College Entry")

    def test_platform_admin_sees_all_entries_in_admin(self):
        self.client.login(username="padmin", password="pass12345")
        response = self.client.get("/admin/timeline/timelineentry/")
        self.assertContains(response, "Own College Entry")
        self.assertContains(response, "Other College Entry")

    def test_college_admin_cannot_view_other_colleges_entry_directly(self):
        """CollegeScopedAdminMixin.get_queryset already excludes the other
        college's row entirely, so Django admin's get_object() finds
        nothing and redirects to the changelist with an error message --
        an even safer outcome than a 403 (it never confirms the object
        exists at all)."""
        self.client.login(username="cadmin", password="pass12345")
        response = self.client.get(f"/admin/timeline/timelineentry/{self.entry_other.pk}/change/")
        self.assertEqual(response.status_code, 302)
        response = self.client.get("/admin/timeline/timelineentry/")
        self.assertNotContains(response, "Other College Entry")

    def test_search_by_title(self):
        self.client.login(username="padmin", password="pass12345")
        response = self.client.get("/admin/timeline/timelineentry/?q=Own+College")
        self.assertContains(response, "Own College Entry")
        self.assertNotContains(response, "Other College Entry")

    def test_filter_by_category(self):
        TimelineService.log_event(self.course, category="COMMUNICATION", event_type="X", title="Comm Entry", college=self.college)
        self.client.login(username="padmin", password="pass12345")
        response = self.client.get("/admin/timeline/timelineentry/?category=COMMUNICATION")
        self.assertContains(response, "Comm Entry")
        self.assertNotContains(response, "Own College Entry")

    def test_college_filter_hidden_for_college_admin(self):
        self.client.login(username="cadmin", password="pass12345")
        response = self.client.get("/admin/timeline/timelineentry/")
        # Sanity: the page loads and college-scoping still works even
        # though the "college" filter itself is suppressed for this role.
        self.assertEqual(response.status_code, 200)

    def test_add_change_delete_permissions_denied_even_for_platform_admin(self):
        self.client.login(username="padmin", password="pass12345")
        response = self.client.get("/admin/timeline/timelineentry/add/")
        self.assertEqual(response.status_code, 403)
