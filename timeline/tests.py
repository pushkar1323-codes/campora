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
