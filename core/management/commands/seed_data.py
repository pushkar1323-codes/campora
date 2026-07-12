"""
Seed sample data for local development and demos.

Idempotent by design: uses get_or_create so it is safe to run multiple
times without creating duplicates. This is the standard production
pattern for seed commands (as opposed to raw Django fixtures, which are
harder to read/maintain and don't dedupe on re-run).

Usage:
    python manage.py seed_data
"""
import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from admissions.models import Enquiry
from courses.models import Course


class Command(BaseCommand):
    help = "Seed the database with sample Campora courses and enquiries for local development."

    def handle(self, *args, **options):
        courses = self._seed_courses()
        self._seed_enquiries(courses)
        self.stdout.write(self.style.SUCCESS("Campora sample data seeded successfully."))

    def _seed_courses(self):
        course_data = [
            {
                "course_name": "B.Tech Computer Science",
                "duration": "4 Years",
                "eligibility": "10+2 with Physics, Chemistry, Mathematics",
                "description": "A comprehensive undergraduate program covering software "
                                "engineering, data structures, algorithms, and modern computing.",
                "is_active": True,
            },
            {
                "course_name": "B.Sc Data Science",
                "duration": "3 Years",
                "eligibility": "10+2 with Mathematics",
                "description": "Focuses on statistics, machine learning, and data analytics "
                                "for real-world decision making.",
                "is_active": True,
            },
            {
                "course_name": "BBA",
                "duration": "3 Years",
                "eligibility": "10+2 in any stream",
                "description": "Business Administration program building management and "
                                "entrepreneurial skills.",
                "is_active": True,
            },
            {
                "course_name": "MBA",
                "duration": "2 Years",
                "eligibility": "Bachelor's degree in any discipline",
                "description": "Postgraduate management program with specializations in "
                                "Finance, Marketing, and HR.",
                "is_active": True,
            },
            {
                "course_name": "B.Com Honours",
                "duration": "3 Years",
                "eligibility": "10+2 with Commerce",
                "description": "In-depth study of accounting, taxation, and finance.",
                "is_active": True,
            },
            {
                "course_name": "Diploma in Mechanical Engineering",
                "duration": "3 Years",
                "eligibility": "10th Pass",
                "description": "Technical diploma no longer accepting new admissions.",
                "is_active": False,
            },
        ]

        created_courses = []
        for data in course_data:
            course, created = Course.objects.get_or_create(
                course_name=data["course_name"], defaults=data
            )
            created_courses.append(course)
            if created:
                self.stdout.write(f"  Created course: {course.course_name}")
        return created_courses

    def _seed_enquiries(self, courses):
        active_courses = [c for c in courses if c.is_active] or courses
        current_year = timezone.localdate().year

        sample_enquiries = [
            {
                "full_name": "Aarav Sharma",
                "father_name": "Rajesh Sharma",
                "email": "aarav.sharma@example.com",
                "mobile": "9876543210",
                "address": "12 MG Road, Kolkata, West Bengal",
                "dob": datetime.date(2007, 4, 12),
                "gender": Enquiry.Gender.MALE,
                "qualification": "12th (Science)",
                "percentage": "88.50",
                "admission_year": current_year,
                "status": Enquiry.Status.NEW,
            },
            {
                "full_name": "Ishita Verma",
                "father_name": "Sanjay Verma",
                "email": "ishita.verma@example.com",
                "mobile": "9812345678",
                "address": "45 Park Street, Kolkata, West Bengal",
                "dob": datetime.date(2006, 9, 3),
                "gender": Enquiry.Gender.FEMALE,
                "qualification": "12th (Commerce)",
                "percentage": "76.20",
                "admission_year": current_year,
                "status": Enquiry.Status.CONTACTED,
            },
            {
                "full_name": "Rohan Mehta",
                "father_name": "Vikram Mehta",
                "email": "rohan.mehta@example.com",
                "mobile": "9900112233",
                "address": "78 Salt Lake, Kolkata, West Bengal",
                "dob": datetime.date(2005, 12, 20),
                "gender": Enquiry.Gender.MALE,
                "qualification": "Bachelor's Degree",
                "percentage": "65.00",
                "admission_year": current_year,
                "status": Enquiry.Status.INTERESTED,
            },
            {
                "full_name": "Sneha Roy",
                "father_name": "Amit Roy",
                "email": "sneha.roy@example.com",
                "mobile": "9765432109",
                "address": "23 Howrah Bridge Road, Howrah, West Bengal",
                "dob": datetime.date(2007, 1, 15),
                "gender": Enquiry.Gender.FEMALE,
                "qualification": "12th (Science)",
                "percentage": "91.10",
                "admission_year": current_year,
                "status": Enquiry.Status.DOCUMENTS_PENDING,
            },
            {
                "full_name": "Kabir Khan",
                "father_name": "Imran Khan",
                "email": "kabir.khan@example.com",
                "mobile": "9654321098",
                "address": "9 New Town, Kolkata, West Bengal",
                "dob": datetime.date(2006, 6, 30),
                "gender": Enquiry.Gender.MALE,
                "qualification": "12th (Commerce)",
                "percentage": "72.40",
                "admission_year": current_year,
                "status": Enquiry.Status.INTERVIEW_SCHEDULED,
            },
            {
                "full_name": "Ananya Das",
                "father_name": "Subrata Das",
                "email": "ananya.das@example.com",
                "mobile": "9543210987",
                "address": "56 Behala, Kolkata, West Bengal",
                "dob": datetime.date(2005, 3, 8),
                "gender": Enquiry.Gender.FEMALE,
                "qualification": "Bachelor's Degree",
                "percentage": "80.75",
                "admission_year": current_year + 1,
                "status": Enquiry.Status.FEE_PENDING,
            },
            {
                "full_name": "Vivaan Gupta",
                "father_name": "Manoj Gupta",
                "email": "vivaan.gupta@example.com",
                "mobile": "9432109876",
                "address": "34 Ballygunge, Kolkata, West Bengal",
                "dob": datetime.date(2006, 11, 25),
                "gender": Enquiry.Gender.MALE,
                "qualification": "12th (Science)",
                "percentage": "95.30",
                "admission_year": current_year,
                "status": Enquiry.Status.ADMITTED,
            },
            {
                "full_name": "Priya Nair",
                "father_name": "Suresh Nair",
                "email": "priya.nair@example.com",
                "mobile": "9321098765",
                "address": "67 Garia, Kolkata, West Bengal",
                "dob": datetime.date(2007, 7, 19),
                "gender": Enquiry.Gender.FEMALE,
                "qualification": "12th (Arts)",
                "percentage": "58.60",
                "admission_year": current_year,
                "status": Enquiry.Status.REJECTED,
            },
            {
                "full_name": "Aditya Singh",
                "father_name": "Rakesh Singh",
                "email": "aditya.singh@example.com",
                "mobile": "9210987654",
                "address": "89 Dum Dum, Kolkata, West Bengal",
                "dob": datetime.date(2006, 2, 14),
                "gender": Enquiry.Gender.MALE,
                "qualification": "12th (Science)",
                "percentage": "83.90",
                "admission_year": current_year,
                "status": Enquiry.Status.NEW,
                "is_deleted": True,  # demonstrates the soft-delete / Recycle Bin feature
            },
        ]

        created_count = 0
        for i, data in enumerate(sample_enquiries):
            data["course"] = active_courses[i % len(active_courses)]
            _, created = Enquiry.all_objects.get_or_create(
                email=data["email"], defaults=data
            )
            if created:
                created_count += 1

        self.stdout.write(f"  Created {created_count} sample enquiries.")
