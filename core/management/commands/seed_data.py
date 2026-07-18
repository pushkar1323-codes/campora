"""
Seed sample data for local development and demos — Campora multi-college
platform edition.

Idempotent by design: uses get_or_create so it is safe to run multiple
times without creating duplicates.

Creates:
- 1 Super Admin user
- 4 Colleges, each APPROVED and each with a College Admin + College Staff user
- 3 courses per college (12 total)
- 4 Student users
- Sample enquiries distributed across colleges/courses, some linked to a
  seeded student account (submitted_by) and some anonymous — reflecting
  that enquiry submission does not yet require login (student auth is a
  future phase).

Usage:
    python manage.py seed_data

All seeded users share the password: Campora@12345
(development/demo only — never use this in production)
"""
import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import StaffProfile, StudentProfile, User
from admissions.models import Enquiry
from courses.models import College, Course

DEV_PASSWORD = "Campora@12345"


class Command(BaseCommand):
    help = "Seed the database with sample Campora colleges, users, courses and enquiries."

    def handle(self, *args, **options):
        self._seed_super_admin()
        colleges = self._seed_colleges()
        students = self._seed_students()
        self._seed_enquiries(colleges, students)
        self.stdout.write(self.style.SUCCESS("Campora sample data seeded successfully."))
        self.stdout.write(self.style.WARNING(f"All seeded users' password: {DEV_PASSWORD}"))

    # -- Users ------------------------------------------------------------

    def _seed_super_admin(self):
        user, created = User.objects.get_or_create(
            username="superadmin",
            defaults={
                "email": "superadmin@campora.local",
                "first_name": "Campora",
                "last_name": "Platform Admin",
                "role": User.Role.SUPER_ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            user.set_password(DEV_PASSWORD)
            user.save()
            self.stdout.write("  Created Super Admin: superadmin")

    def _seed_college_staff(self, college, username_prefix, role, first_name, last_name, designation):
        user, created = User.objects.get_or_create(
            username=f"{username_prefix}_{college.slug}".replace("-", "_")[:150],
            defaults={
                "email": f"{username_prefix}@{college.slug}.campora.local",
                "first_name": first_name,
                "last_name": last_name,
                "role": role,
                # is_staff=True only for COLLEGE_ADMIN: required to log into
                # the Campora Administration Panel at all (Django's own
                # AdminAuthenticationForm hard-requires is_staff, regardless
                # of our custom CamporaAdminSite.has_permission() check —
                # see core/admin_site.py). What they can actually see/do
                # once inside is then scoped to their own college by
                # core/admin_mixins.py, not by this flag. COLLEGE_STAFF
                # intentionally gets no admin access at all, per the
                # Admin Panel Upgrade spec — they keep using the
                # college-scoped dashboard only.
                "is_staff": role == User.Role.COLLEGE_ADMIN,
            },
        )
        if created:
            user.set_password(DEV_PASSWORD)
            user.save()

        StaffProfile.objects.get_or_create(
            user=user,
            defaults={"college": college, "designation": designation, "phone": "9800000000"},
        )
        return user

    def _seed_students(self):
        student_data = [
            ("priya_sharma", "Priya", "Sharma"),
            ("arjun_mehta", "Arjun", "Mehta"),
            ("neha_kapoor", "Neha", "Kapoor"),
            ("rahul_verma", "Rahul", "Verma"),
        ]
        students = []
        for username, first, last in student_data:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.com",
                    "first_name": first,
                    "last_name": last,
                    "role": User.Role.STUDENT,
                },
            )
            if created:
                user.set_password(DEV_PASSWORD)
                user.save()
            StudentProfile.objects.get_or_create(
                user=user, defaults={"phone": "9700000000"}
            )
            students.append(user)
        return students

    # -- Colleges & Courses -------------------------------------------------

    def _seed_colleges(self):
        college_data = [
            {
                "name": "Campora Institute of Technology",
                "short_description": "Engineering and technology programs with an industry focus.",
                "description": "Campora Institute of Technology offers rigorous, hands-on "
                                "engineering and computing programs, preparing graduates for "
                                "careers in software, data, and core engineering fields.",
                "city": "Kolkata",
                "state": "West Bengal",
                "address": "12 Tech Park Road, Salt Lake, Kolkata",
                "phone": "9811100001",
                "email": "admissions@cit.campora.local",
                "website": "https://cit.campora.local",
                "status": College.Status.APPROVED,
                "courses": [
                    ("B.Tech Computer Science", "4 Years", "10+2 with Physics, Chemistry, Mathematics",
                     "Software engineering, data structures, algorithms, and modern computing.", True),
                    ("B.Sc Data Science", "3 Years", "10+2 with Mathematics",
                     "Statistics, machine learning, and data analytics for real-world decisions.", True),
                    ("Diploma in Mechanical Engineering", "3 Years", "10th Pass",
                     "Technical diploma, currently not accepting new admissions.", False),
                ],
            },
            {
                "name": "Campora College of Business",
                "short_description": "Business, management, and commerce programs.",
                "description": "Campora College of Business builds management and "
                                "entrepreneurial skills through practical, industry-linked "
                                "coursework across business, finance, and commerce.",
                "city": "Mumbai",
                "state": "Maharashtra",
                "address": "45 Commerce Avenue, Andheri, Mumbai",
                "phone": "9811100002",
                "email": "admissions@ccb.campora.local",
                "website": "https://ccb.campora.local",
                "status": College.Status.APPROVED,
                "courses": [
                    ("BBA", "3 Years", "10+2 in any stream",
                     "Foundational business administration and management program.", True),
                    ("MBA", "2 Years", "Bachelor's degree in any discipline",
                     "Postgraduate management program with Finance, Marketing and HR tracks.", True),
                    ("B.Com Honours", "3 Years", "10+2 with Commerce",
                     "In-depth study of accounting, taxation, and finance.", True),
                ],
            },
            {
                "name": "Campora School of Design",
                "short_description": "Creative design and media programs.",
                "description": "Campora School of Design nurtures creative talent across "
                                "visual design, media, and communication disciplines.",
                "city": "Bengaluru",
                "state": "Karnataka",
                "address": "78 Design District, Indiranagar, Bengaluru",
                "phone": "9811100003",
                "email": "admissions@csd.campora.local",
                "website": "https://csd.campora.local",
                "status": College.Status.APPROVED,
                "courses": [
                    ("B.Des Communication Design", "4 Years", "10+2 in any stream",
                     "Visual communication, branding, and media design.", True),
                    ("B.Des Product Design", "4 Years", "10+2 in any stream",
                     "Industrial and product design fundamentals and studio practice.", True),
                    ("Diploma in UI/UX Design", "1 Year", "10+2 in any stream",
                     "Practical, portfolio-driven UI/UX design program.", True),
                ],
            },
            {
                "name": "Greenfield College of Arts & Science",
                "short_description": "A partner college offering liberal arts and science programs.",
                "description": "Greenfield College of Arts & Science is a Campora partner "
                                "institution offering a broad liberal arts and sciences "
                                "curriculum.",
                "city": "Pune",
                "state": "Maharashtra",
                "address": "23 Greenfield Road, Pune",
                "phone": "9811100004",
                "email": "admissions@greenfield.campora.local",
                "website": "https://greenfield.campora.local",
                "status": College.Status.APPROVED,
                "courses": [
                    ("B.A. Economics", "3 Years", "10+2 in any stream",
                     "Foundational and applied economics.", True),
                    ("B.Sc Physics", "3 Years", "10+2 with Science",
                     "Core and applied physics with lab-based coursework.", True),
                    ("B.A. English Literature", "3 Years", "10+2 in any stream",
                     "Literary studies, critical theory, and writing.", True),
                ],
            },
        ]

        colleges = []
        for data in college_data:
            course_list = data.pop("courses")
            college, created = College.objects.get_or_create(
                name=data["name"], defaults=data
            )
            if created:
                self.stdout.write(f"  Created college: {college.name}")

            self._seed_college_staff(
                college, "admin", User.Role.COLLEGE_ADMIN,
                "Admin", college.name.split()[0], "College Admin"
            )
            self._seed_college_staff(
                college, "staff", User.Role.COLLEGE_STAFF,
                "Staff", college.name.split()[0], "Admissions Counsellor"
            )

            for course_name, duration, eligibility, description, is_active in course_list:
                Course.objects.get_or_create(
                    college=college,
                    course_name=course_name,
                    defaults={
                        "duration": duration,
                        "eligibility": eligibility,
                        "description": description,
                        "is_active": is_active,
                    },
                )
            colleges.append(college)
        return colleges

    # -- Enquiries ----------------------------------------------------------

    def _seed_enquiries(self, colleges, students):
        current_year = timezone.localdate().year

        # (college_index, course_index, student_or_None, enquiry-field overrides)
        plan = [
            (0, 0, students[0], dict(full_name="Aarav Sharma", father_name="Rajesh Sharma",
             email="aarav.sharma@example.com", mobile="9876543210",
             dob=datetime.date(2007, 4, 12), gender=Enquiry.Gender.MALE,
             qualification="12th (Science)", percentage="88.50",
             status=Enquiry.Status.NEW)),
            (0, 1, None, dict(full_name="Ishita Verma", father_name="Sanjay Verma",
             email="ishita.verma@example.com", mobile="9812345678",
             dob=datetime.date(2006, 9, 3), gender=Enquiry.Gender.FEMALE,
             qualification="12th (Commerce)", percentage="76.20",
             status=Enquiry.Status.CONTACTED)),
            (1, 0, students[1], dict(full_name="Rohan Mehta", father_name="Vikram Mehta",
             email="rohan.mehta@example.com", mobile="9900112233",
             dob=datetime.date(2005, 12, 20), gender=Enquiry.Gender.MALE,
             qualification="Bachelor's Degree", percentage="65.00",
             status=Enquiry.Status.INTERESTED)),
            (1, 1, None, dict(full_name="Sneha Roy", father_name="Amit Roy",
             email="sneha.roy@example.com", mobile="9765432109",
             dob=datetime.date(2007, 1, 15), gender=Enquiry.Gender.FEMALE,
             qualification="12th (Science)", percentage="91.10",
             status=Enquiry.Status.DOCUMENTS_PENDING)),
            (1, 2, students[2], dict(full_name="Kabir Khan", father_name="Imran Khan",
             email="kabir.khan@example.com", mobile="9654321098",
             dob=datetime.date(2006, 6, 30), gender=Enquiry.Gender.MALE,
             qualification="12th (Commerce)", percentage="72.40",
             status=Enquiry.Status.INTERVIEW_SCHEDULED)),
            (2, 0, None, dict(full_name="Ananya Das", father_name="Subrata Das",
             email="ananya.das@example.com", mobile="9543210987",
             dob=datetime.date(2005, 3, 8), gender=Enquiry.Gender.FEMALE,
             qualification="12th (Arts)", percentage="80.75",
             status=Enquiry.Status.FEE_PENDING, admission_year=current_year + 1)),
            (2, 1, students[3], dict(full_name="Vivaan Gupta", father_name="Manoj Gupta",
             email="vivaan.gupta@example.com", mobile="9432109876",
             dob=datetime.date(2006, 11, 25), gender=Enquiry.Gender.MALE,
             qualification="12th (Arts)", percentage="95.30",
             status=Enquiry.Status.ADMITTED)),
            (3, 0, None, dict(full_name="Priya Nair", father_name="Suresh Nair",
             email="priya.nair@example.com", mobile="9321098765",
             dob=datetime.date(2007, 7, 19), gender=Enquiry.Gender.FEMALE,
             qualification="12th (Arts)", percentage="58.60",
             status=Enquiry.Status.REJECTED)),
            (3, 1, None, dict(full_name="Aditya Singh", father_name="Rakesh Singh",
             email="aditya.singh@example.com", mobile="9210987654",
             dob=datetime.date(2006, 2, 14), gender=Enquiry.Gender.MALE,
             qualification="12th (Science)", percentage="83.90",
             status=Enquiry.Status.NEW, is_deleted=True)),  # demonstrates soft-delete
        ]

        created_count = 0
        for college_idx, course_idx, student, fields in plan:
            college = colleges[college_idx]
            active_courses = list(college.courses.filter(is_active=True)) or list(college.courses.all())
            course = active_courses[course_idx % len(active_courses)]

            fields.setdefault("admission_year", current_year)
            fields["course"] = course
            fields["submitted_by"] = student
            fields["address"] = f"Sample Address, {college.city}"

            _, created = Enquiry.all_objects.get_or_create(
                email=fields["email"], defaults=fields
            )
            if created:
                created_count += 1

        self.stdout.write(f"  Created {created_count} sample enquiries.")
