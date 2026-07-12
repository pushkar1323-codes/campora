# Campora – College Admission & Student Enquiry Portal

**Campora** is a modern web-based College Admission & Student Enquiry Portal
that enables educational institutions to efficiently manage admission
enquiries, student registrations, counselling, admission workflows, course
management, and administrative operations through a secure, user-friendly
platform.

> "Connecting Students with the Right Future."

Developed by **Pushkar Srivastava**. © 2026 Campora. All Rights Reserved.

Prospective students submit admission enquiries through the public site,
while college staff manage, search, update, filter, export and analyze
those enquiries through the Campora dashboard. Data is stored in MySQL
(Amazon RDS in production) and the application is deployed on AWS EC2.

_Note: internal project/package name (`college_admission`), Django app names
(`core`, `accounts`, `admissions`, `courses`, `dashboard`), database name
(`college_admission_db`), and folder structure are unchanged per the
technical architecture — only user-facing branding is "Campora"._

## Features

Implemented so far:
- Project foundation: Django project + 5 modular apps (`core`, `accounts`,
  `admissions`, `courses`, `dashboard`)
- Campora branding: navbar, footer, admin site, design system
- Bootstrap 5 responsive base template with sticky navbar and footer
- Static/media file configuration
- Local MySQL database configuration via environment variables
- **Database models**: `Course` (courses app) and `Enquiry` (admissions app)
  with FK relationship, soft-delete support (via a custom manager), field
  validators, and indexes — see `DATABASE_DESIGN.docx`
- Django admin registered for both models: search, filters, soft-delete
  actions
- Idempotent sample data seeding via `python manage.py seed_data`

Planned (see `IMPLEMENTATION_PLAN.docx` for the full phase roadmap):
Public website content, Admission Enquiry form, CRUD, Search/Filter,
Dashboard with charts, Authentication, CSV/Excel export, AWS deployment.

## Technology Stack

Python, Django 5.2 (LTS), Bootstrap 5, JavaScript, MySQL, AWS (EC2, RDS, EBS, IAM, S3).
Campora design system: Poppins (headings) + Inter (body), Lucide icons,
color palette defined in `static/css/style.css`.

## Project Structure

```
college_admission/
├── accounts/         # Authentication & staff management
├── admissions/        # Admission enquiry CRUD (Enquiry model)
├── courses/          # Course management (Course model)
├── dashboard/         # Analytics & reports
├── core/              # Public website (Home, About, Contact) + seed_data command
├── config/            # Django project settings, root URLs, WSGI/ASGI
├── templates/          # Base template + partials (navbar, footer, messages)
├── static/            # css, js, images
├── media/              # User-uploaded files
├── manage.py
├── requirements.txt
├── .env.example
└── README.md
```

## Installation

1. Clone the repository.
2. Create and activate a virtual environment:
   ```
   python3 -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```
3. Install requirements:
   ```
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and fill in real values:
   ```
   cp .env.example .env
   ```
5. Create the local MySQL database (matching `.env` `DB_NAME`):
   ```sql
   CREATE DATABASE college_admission_db CHARACTER SET utf8mb4;
   ```
6. Run migrations:
   ```
   python manage.py migrate
   ```
7. (Optional) Seed sample courses and enquiries for local development:
   ```
   python manage.py seed_data
   ```
8. Create an admin/staff account to access the Django admin:
   ```
   python manage.py createsuperuser
   ```
9. Start the development server:
   ```
   python manage.py runserver
   ```
   Visit `http://127.0.0.1:8000/admin/` and log in to manage Courses and
   Enquiries.

## Environment Variables

Defined in `.env` (see `.env.example`):

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` in development, `False` in production |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hosts |
| `DB_NAME` | MySQL database name |
| `DB_USER` | MySQL user |
| `DB_PASSWORD` | MySQL password |
| `DB_HOST` | MySQL host |
| `DB_PORT` | MySQL port (default `3306`) |

## Usage

Students will be able to submit admission enquiries through the public site
(built in Phase 4). Staff will log in (Phase 9) to manage, search, filter,
update and export enquiries via the dashboard (Phases 5–11).

## AWS Deployment

Planned for Phases 13–14: EC2 + Gunicorn + Nginx + Amazon RDS + EBS + S3.
Not yet implemented.

## Testing Checklist

- [x] Phase 1: `python manage.py check` passes, static files collect, all
      routes return correct HTTP responses, base template renders correctly
- [x] Phase 2: Migrations apply cleanly (`courses.0001_initial`,
      `admissions.0001_initial`); `seed_data` command is idempotent; model
      validators correctly reject invalid mobile numbers, out-of-range
      percentages, and past admission years; soft-delete manager correctly
      excludes deleted records by default; Django admin verified end-to-end
      (login, Course list, Enquiry list including soft-deleted rows)
- [ ] CRUD, Search, Filters, Authentication, full Dashboard — not yet built
      (future phases)

## Future Enhancements

SMS notifications, document uploads, advanced reporting (see `PROJECT_BRAIN.docx`).

## Contributors

Add team member names here.

## License

Educational / College Project.
