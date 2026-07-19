from django.test import TestCase
from django.urls import reverse

from .models import StudentProfile, User


class StudentProfileOwnershipTests(TestCase):
    """Phase 1, Feature 1/2: a Student can view/edit only their own
    profile. Registration (StudentSignUpForm) is untouched by this phase
    -- profile editing happens post-login through this view instead."""

    def setUp(self):
        self.student = User.objects.create_user(
            username="student1", password="pass12345", role=User.Role.STUDENT, email="s1@example.com",
        )
        StudentProfile.objects.create(user=self.student, phone="9999999999", address="Old address")
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role=User.Role.COLLEGE_STAFF, is_staff=True)

    def test_student_can_view_own_profile(self):
        self.client.login(username="student1", password="pass12345")
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "9999999999")

    def test_student_can_update_own_profile(self):
        self.client.login(username="student1", password="pass12345")
        self.client.post(reverse("accounts:profile"), {
            "first_name": "Updated", "last_name": "Name", "email": "new@example.com",
            "phone": "1231231234", "date_of_birth": "2000-05-05", "address": "New Address",
        })
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, "Updated")
        self.assertEqual(self.student.email, "new@example.com")
        self.assertEqual(self.student.student_profile.phone, "1231231234")

    def test_staff_cannot_reach_student_profile_view(self):
        self.client.login(username="staff1", password="pass12345")
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_registration_form_unchanged_by_phase_1(self):
        """Sanity guard: registration keeps working exactly as before --
        profile completion (gender/profile-picture-style extras) was
        deliberately NOT added to StudentSignUpForm this phase."""
        response = self.client.post(reverse("accounts:register"), {
            "username": "newstudent", "password1": "SuperSecret123!", "password2": "SuperSecret123!",
            "first_name": "New", "last_name": "Student", "email": "newstudent@example.com",
            "phone": "9998887777", "date_of_birth": "2001-01-01", "address": "Some address",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="newstudent").exists())
