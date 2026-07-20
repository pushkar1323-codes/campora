# Campora – College Admission & Student Enquiry Portal

**Campora** is a centralized, multi-college SaaS admission and student
enquiry platform. Colleges register and manage their own admission process
on Campora; students discover colleges, browse courses, and submit
admission enquiries — all from one platform, instead of visiting a dozen
different college websites.

> "Connecting Students with the Right Future."

Developed by **Pushkar Srivastava**. © 2026 Campora. All Rights Reserved.

**Platform roles**: Super Admin (manages the platform), College Admin /
College Staff (manage their own college's courses and enquiries), and
Student (browses colleges, submits enquiries). See "Architecture" below.

Data is stored in MySQL (Amazon RDS in production) and the application is
deployed on AWS EC2.

_Note: internal project/package name (`college_admission`), Django app names
(`core`, `accounts`, `admissions`, `courses`, `dashboard`), database name
(`college_admission_db`), and folder structure are unchanged — only
user-facing branding is "Campora."_

## Features

Implemented so far:
- Project foundation: Django project + 5 modular apps (`core`, `accounts`,
  `admissions`, `courses`, `dashboard`)
- Campora branding: navbar, footer, admin site, design system
- Bootstrap 5 responsive base template with sticky navbar and footer
- Static/media file configuration
- Local MySQL database configuration via environment variables
- **Multi-college platform architecture**:
  - Custom `User` model (`accounts.User`) with 4 roles: Super Admin,
    College Admin, College Staff, Student — see "Architecture & Roles"
  - `StudentProfile` / `StaffProfile` role-extension models
  - `College` model (`courses` app) with an approval-workflow `status`
    field (Pending/Approved/Rejected/Suspended) — only Approved colleges
    are ever shown publicly
  - `Course` belongs to exactly one `College`; course names are unique
    **per college**, not globally (two colleges can both offer "BBA")
  - `Enquiry` references both `College` and `Course` — `college` is
    auto-derived from `course.college` on save and is not independently
    editable, so the two can never drift out of sync
  - Soft-delete support on `Enquiry` via a custom manager, field
    validators, and database indexes
- Django admin registered for all models: search, filters, fieldsets, and
  actions (soft-delete/restore on Enquiry; approve/reject/suspend on
  College)
- Idempotent sample data seeding via `python manage.py seed_data`
  (colleges, college admins/staff, students, courses, enquiries)
- **Full public website**: Home (hero, platform stats, featured colleges,
  why-choose-us, CTA), About (platform mission/vision/values), **Colleges**
  (searchable/filterable directory), **College Detail** (profile, contact
  info, active courses, gallery placeholder, at-a-glance stats), Courses
  (grouped by college), Contact (platform-level, validated enquiry form)
- Reusable `course_card` / `college_card` template partials
- Structured logging configured (console handler, per-app loggers)
- **Admission Enquiry submission** (Phase 4): students submit a course-
  specific enquiry directly from a college's "Enquire Now" button — no
  College/Course dropdown to fill in, since the course (and its college)
  is fixed by the page the student came from. Works anonymously per
  Version 1.0 scope; auto-links the enquiry to a logged-in Student's
  account when one is signed in. Server-side validated (Django Forms,
  reusing the existing field validators), Post/Redirect/Get, with a
  confirmation page showing a reference number.
- **Enquiry Management** (Phase 5): staff-facing listing (paginated,
  20/page) and detail views under `/dashboard/enquiries/`. Platform Admin
  sees every enquiry; College Admin/Staff see only their own college's
  enquiries (ownership-enforced — another college's enquiry 404s rather
  than 403s, so its existence isn't even confirmed). Every row/detail page
  always shows the associated College and Course.
- **Search, Filter & Sorting** (Phase 6): the enquiry listing now supports
  live search (student name, mobile, email, college or course — matches
  any of them), filters (college — Platform Admin only, course, gender,
  status, admission year), and sortable columns (student name, college,
  course, submission date, either direction). All combine together (AND),
  pagination preserves the active search/filter/sort across pages, and a
  malformed or hand-edited querystring degrades gracefully to "no filter"
  instead of erroring. College Admin/Staff never get a college filter and
  their course choices are restricted to their own college — the same
  ownership rule the rest of the dashboard follows.
- **Update Module** (Phase 7): staff can now edit any field on an
  enquiry — including reassigning its College and Course — from
  `/dashboard/enquiries/<id>/edit/`. The College and Course dropdowns are
  a genuine pair: picking a College narrows the Course dropdown (a small
  progressive-enhancement script for Platform Admin; College Admin/Staff
  simply never see other colleges' courses at all), and the pairing is
  re-validated server-side regardless of what the browser sent
  (`course.college` must match the selected `college`, or the form is
  redisplayed with a field-level error). This does **not** loosen the
  "college is auto-derived from course" rule above — the College
  dropdown drives validation/UX, but saving the form still only ever
  changes `course`, and `Enquiry.save()` re-derives `college` from it the
  same way it always has. College Admin/Staff get a College field that's
  rendered `disabled`, so even a hand-crafted POST body can't move an
  enquiry to another college — Django disabled fields always use their
  server-set initial value and silently ignore submitted data. Success
  and validation-error messages both surface via the existing Bootstrap
  alert / Django-messages integration.
- **Delete & Restore** (Phase 8): enquiries are soft-deleted by default —
  "delete" (from the enquiry list or detail page, with a confirm prompt)
  moves an enquiry to a **Recycle Bin** (`/dashboard/enquiries/recycle-bin/`)
  rather than removing it, so there is never a one-click, irreversible
  data-loss action. From the Recycle Bin, any staff role that manages
  enquiries can **Restore** a record back to the active list. **Permanent
  deletion** is a deliberate second step, restricted to administrators
  (Platform Admin / College Admin — College Staff can soft-delete and
  restore but not permanently delete) and can *only* be performed on a
  record that's already in the Recycle Bin — there's no path from the
  active list straight to permanent deletion. College ownership scoping
  applies throughout: a College Admin/Staff user's Recycle Bin only shows
  their own college's deleted enquiries, and delete/restore/permanent-
  delete on another college's enquiry 404s the same way the rest of the
  dashboard does. This uses the soft-delete manager (`Enquiry.objects` /
  `Enquiry.all_objects`, `is_deleted`, `soft_delete()`/`restore()`) that
  was already built into the model back in Phase 2/Platform Refactor —
  every Phase 4–7 query already excluded soft-deleted rows automatically,
  so this phase only had to add the delete/restore/recycle-bin views
  themselves.
- **Dashboard** (Phase 10): both role dashboards (Platform Admin,
  College Admin/Staff) now have the full at-a-glance layout — summary
  cards (already existed from the Platform Refactor), a **Recent
  Enquiries** table (new on the Platform dashboard; already existed on
  the College dashboard), **Chart.js** analytics, and quick-action
  buttons. Charts: the Platform dashboard gets an **enquiries-by-college**
  bar chart and a platform-wide **enquiries-by-status** doughnut; the
  College dashboard gets its own **enquiries-by-status** doughnut scoped
  to that college. ("College-wise" analytics only makes sense at the
  Platform Admin's cross-college view — there's nothing to compare across
  colleges from inside a single college's dashboard, so that chart is
  Platform-only by design.) Both charts include **every** category —
  every college, every status — even ones with zero enquiries, rather
  than silently omitting them, so the chart can't be misread as "that
  college/status doesn't have any data" when it might just not have
  loaded. Chart data is passed to the template via Django's `json_script`
  filter (never string-built into a `<script>` tag), and Chart.js itself
  is loaded only on these two dashboard pages, not site-wide. A new
  "Recycle Bin" quick-action button was added to both dashboards for
  parity with the one already on the enquiry list (Phase 8).
- **Campora Administration Panel** (Admin Panel Upgrade — not a numbered
  IMPLEMENTATION_PLAN.docx phase; a standalone enhancement, same as the
  Platform Refactor was): a fully custom, branded, role-scoped Django
  admin at `/admin/`, replacing the default Django admin entirely. See
  the dedicated **Administration Panel** section below for the full
  architecture, security model, and testing detail.

- **Secure Admission Workflow** (not a numbered `IMPLEMENTATION_PLAN.docx`
  phase — Phase 1 of a separate Master Implementation Roadmap): personal
  information (name/email/phone/address/DOB) is owned and edited only by
  the student who owns it — never by College Staff/Admin, who instead use
  a **Request Correction** workflow; a student may self-edit their own
  enquiry's admission-workflow fields for a configurable window after
  submission; Platform Admin retains a full-access override, the only
  path to correct an anonymous/guest enquiry's data.
- **Enterprise Communication System** (Phase 2A of the same roadmap): a
  reusable `communication` app — `MessageThread`/`ThreadParticipant`/
  `Message`, generic via `ContentType` so it isn't tied to `Enquiry` and
  can be reused by future modules (Hostel, Scholarships, Placements, ...)
  without redesign. All access goes through `CommunicationService` —
  no other app touches `ContentType`/`GenericForeignKey` directly.
  Students and staff exchange messages per-enquiry, with edit/soft-delete,
  read-status tracking, and automatic system messages (e.g. a Correction
  Request being opened posts one automatically).

Planned (see `IMPLEMENTATION_PLAN.docx` for the full phase roadmap):
CSV/Excel export, AWS deployment.

## Administration Panel

`/admin/` now serves the **Campora Administration Panel** — a custom
`django.contrib.admin.AdminSite` subclass (`core/admin_site.py`), not
Django's default admin. The default `admin.site` is never registered
into or wired up anywhere in this project.

### Who gets in, and how

Per the Admin Panel Upgrade spec, **only Platform Admin and College
Admin** can access the panel at all — College Staff and Student keep
using their existing dashboards exclusively, with no admin access
whatsoever.

Two separate checks have to both pass:

1. **`user.is_staff=True`** — required by Django's own
   `AdminAuthenticationForm` at the login form itself, before our custom
   logic even runs. `seed_data.py` and `accounts/forms.py::StaffCreationForm`
   now set this for `COLLEGE_ADMIN` accounts only (not `COLLEGE_STAFF`).
   This flag only gets a user *in the door* — it grants no visibility or
   permissions by itself.
2. **`CamporaAdminSite.has_permission()`** — the real, server-side gate,
   checked by Django admin on every single request. Checks
   `request.user.role` directly (Platform Admin or College Admin only),
   the same authorization model (`accounts.User.role`) the rest of this
   app already uses — not Django's built-in permission/group system,
   which none of Campora's role-based accounts have ever used.

### Multi-college data isolation

A College Admin only ever sees, and can only ever act on, their **own**
college's data — enforced server-side by `core/admin_mixins.py`
(`CamporaAdminAccessMixin` for role gating, `CollegeScopedAdminMixin` for
per-college scoping), applied to every relevant `ModelAdmin`:

- **Enforced at three separate layers**, matching the spec's "do NOT rely
  on hiding menu items" requirement:
  - `get_queryset()` — another college's rows never appear in any list,
    search, or autocomplete.
  - `has_view/change/delete_permission(request, obj)` — **object-level**,
    so a guessed URL for another college's object (e.g.
    `/admin/courses/course/17/change/`) is denied even though it's not
    in the visible list. Django's own admin then shows this as a
    friendly "object doesn't exist" redirect rather than a raw 403 for
    already-filtered-out objects — the object's existence is never
    confirmed to a College Admin who isn't allowed to see it, the same
    "404 not 403 across colleges" principle the dashboard app already
    uses everywhere else (Phases 4–8).
  - `formfield_for_foreignkey()` — a College Admin's dropdowns (e.g.
    "College" on the Course form, "Course" on the Enquiry form) only
    ever offer their own college's choices, so they can't move a
    Course/Enquiry to another college even by editing an existing,
    in-scope row.

| Model | Platform Admin | College Admin |
| --- | --- | --- |
| College | Full CRUD | View/edit own college's profile only — cannot add or delete (lifecycle stays owned by the existing approve/reject/suspend workflow) |
| Course | Full CRUD | Full CRUD, own college only |
| StaffProfile | Full CRUD | Full CRUD, own college only ("Own Staff") |
| Enquiry | Full CRUD (incl. soft-deleted — `all_objects`, unchanged from before) | Full CRUD, own college only, same `all_objects` visibility |
| User, Group | Full access | **No access at all** — spec explicitly lists these among what a College Admin "must never see" |
| StudentProfile | Full access | **No access.** Flagged judgment call: `StudentProfile` has no `college` FK in the current data model (a student isn't owned by any one college), so there's no correct subset of "own students" to show — rather than guess, this stays Platform-Admin-only |

### Branding

`templates/admin/base_site.html` (covers the login page too, since
Django's `admin/login.html` extends `base_site.html`) and
`static/css/admin-campora.css` re-skin the panel using the same
`--brand-primary` / `--brand-accent` colors as the public site, re-skin
the header/footer, and replace "Django administration" throughout with
"Campora Administration Panel".

### Admin dashboard (`/admin/` index)

`CamporaAdminSite.index()` (`core/admin_site.py`) injects real,
role-scoped stats above the standard app list — rendered by
`templates/admin/index.html`:

- **Summary cards**: Total Colleges, Pending College Approvals, Total
  Courses, Total Students, Total Staff, Total Enquiries, New/Pending
  Enquiries, Today's Enquiries, In Recycle Bin (Platform Admin sees
  platform-wide numbers; College Admin sees only their own college's).
- **Latest Admissions**: the 5 most recent enquiries in scope.
- **Recent Activity**: sourced from Django admin's own `LogEntry` audit
  table — genuinely real data every admin action already generates, not
  a placeholder. Platform Admin sees everyone's recent actions; College
  Admin sees their own. Django's default "My actions" sidebar module is
  also kept as-is.
- **System Status**: Debug Mode on/off, Database connectivity — real,
  honestly-scoped operational facts rather than fabricated metrics
  (Platform Admin only).
- **Quick Links** to the most-used changelists.
- **Audit Logs** (`/admin/admin/logentry/`): Django's `LogEntry` model,
  registered read-only (view-only — no add/change/delete, verified by
  actually POSTing a change attempt and confirming it's rejected),
  Platform-Admin-only.

### Quick Actions on the app's own dashboards

Per the spec, both `dashboard/platform_dashboard.html` and
`dashboard/college_dashboard.html` also gained a Quick Actions card grid
(matching the existing card/hover design language —
`.quick-action-card` in `static/css/style.css`). Link choices, flagged
for visibility:

- **Admission Enquiries** and College Admin's **Manage Staff** link to
  the existing, already-built dashboard pages (better UX than raw admin
  CRUD) — not the admin panel.
- **Manage Colleges / Courses / Users** and **Audit Logs** link into the
  new admin panel, since no dedicated in-app CRUD UI exists yet for
  those (Manage Colleges/Courses is Phase 12).
- **Platform/College Analytics** scroll-anchor (`#analytics`) to the
  Chart.js section already on that same dashboard page (Phase 10) —
  no new page.
- **Reports** and **Platform Settings** don't correspond to anything
  built yet, so they're rendered as visibly disabled "Coming Soon"
  cards rather than a dead link or an invented page.
- Admin-panel-linked and admin-only actions (Administration Panel,
  Manage Courses, Manage Staff, Reports) are hidden entirely from
  College Staff on the college dashboard, since that role has no admin
  access at all — showing them a link that just 403s would be poor UX.

## Architecture & Roles

Campora uses **one custom Django user model** (`accounts.User`) with a
`role` field, rather than separate authentication systems per role:

| Role | Scope |
|---|---|
| **Super Admin** | Manages the whole platform: approves/rejects/suspends colleges, manages users, views platform-wide analytics |
| **College Admin** | Manages their own college's profile, courses, staff, and enquiries |
| **College Staff** | Works under a College Admin: views/updates enquiries assigned to their college |
| **Student** | Browses colleges/courses, submits enquiries, (future) tracks enquiry status |

Data model: `User` → `StudentProfile` (Student role) or `StaffProfile`
(College Admin / College Staff role, linked to a `College`).

## Authentication & Authorization

Login/logout, registration, and role-based access control were all built
during the Platform Refactor — ahead of their originally-numbered slot in
`IMPLEMENTATION_PLAN.docx` (Phase 9), because the multi-college
architecture couldn't be meaningfully built or tested without them. Phase
9 in this codebase is a **verification pass** confirming the existing
implementation already satisfies its spec in full, rather than new
functionality (see PHASE_STATUS.docx and CHANGELOG.md `[0.9.1]` for the
verification details).

- **Login / logout**: Django's built-in `LoginView`/`LogoutView`
  (`accounts/views.py`, `accounts/urls.py`) with Campora-branded Bootstrap
  5 templates. Logout is a POST-only form (not a GET link) in the navbar
  — required by Django 5.x's `LogoutView` for CSRF safety.
- **Registration**: self-service student sign-up only
  (`accounts/views.py::register_student`) — College Admin/Staff accounts
  are provisioned by a College Admin via `/dashboard/college/staff/`, not
  self-registered, matching the platform's role hierarchy.
- **Every management page requires login.** `dashboard/views.py`'s
  entry point (`dashboard_home`) and every dashboard view is decorated
  with either `@login_required` or `@role_required(...)`
  (`accounts/decorators.py`) — there is no dashboard/management URL that
  skips this. Public pages (Home, Colleges, Course browsing, Contact,
  and submitting an enquiry) intentionally remain open to anonymous
  visitors, per `PROJECT_BRAIN.docx`'s Version 1.0 scope ("Students
  submit enquiries without authentication").
- **Redirect behaviour is intentionally split in two**, matching Django
  best practice rather than blanket-redirecting everyone:
  - **Anonymous** users hitting any protected page are redirected to
    `/accounts/login/?next=<original URL>` — logging in then lands them
    back on the page they actually wanted, not just the dashboard root.
  - **Authenticated users with the wrong role** (e.g. a Student hitting
    `/dashboard/platform/`, or College Staff hitting the admin-only
    `/dashboard/college/staff/` or a permanent-delete URL) get a genuine
    **403 Forbidden**, not a redirect — silently redirecting an
    authenticated user who is deliberately trying (or accidentally
    linked into) a page they can't use would either loop confusingly or
    mask the permission error.
- **College ownership**, layered on top of role checks, is enforced by
  `accounts/decorators.py::get_staff_college` everywhere a College
  Admin/Staff user touches data — see Phases 4–8 above for the many
  cross-college-access tests (all 404, never 403, so another college's
  data is never even confirmed to exist).

## Technology Stack

Python, Django 5.2 (LTS), Bootstrap 5, JavaScript, MySQL, AWS (EC2, RDS, EBS, IAM, S3).
Campora design system: Poppins (headings) + Inter (body), Lucide icons,
color palette defined in `static/css/style.css`.

## Project Structure

```
college_admission/
├── accounts/         # Custom User model (4 roles), StudentProfile,
│                     # StaffProfile, authentication (login/register)
├── admissions/        # Enquiry model + course-specific enquiry submission
│                     # form/views (College + Course + optional submitted_by)
├── courses/          # College model (approval workflow) + Course model
├── dashboard/         # Role-scoped dashboards (Platform/College/Student)
│                     # + staff-facing Enquiry Management (listing/detail)
├── communication/     # Reusable Communication System (MessageThread,
│                     # ThreadParticipant, Message) -- generic, not tied
│                     # to Enquiry; see CommunicationService
├── core/              # Public website (Home, About, Colleges, Courses,
│                     # Contact) + seed_data command
├── config/            # Django project settings, root URLs, WSGI/ASGI
├── templates/          # Base template + partials (navbar, footer, messages)
├── static/            # css, js, images
├── media/              # User-uploaded files (college logos/cover images)
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
6. **If you have an existing local database from before this phase**, drop
   and recreate it (see "⚠️ Breaking Change" below — this phase introduces
   a custom user model, which Django cannot apply on top of an already
   migrated default `auth.User` table):
   ```sql
   DROP DATABASE college_admission_db;
   CREATE DATABASE college_admission_db CHARACTER SET utf8mb4;
   ```
7. Run migrations:
   ```
   python manage.py migrate
   ```
8. Seed sample colleges, users (Platform Admin, College Admins/Staff,
   Students), courses and enquiries:
   ```
   python manage.py seed_data
   ```
   All seeded users share the password `Campora@12345` (development only).
   Notable seeded logins: `superadmin`, `admin_campora_institute_of_technology`,
   `staff_campora_institute_of_technology`, `priya_sharma` (student).
9. (Optional) Create your own Django superuser for `/admin/`:
   ```
   python manage.py createsuperuser
   ```
10. Start the development server:
    ```
    python manage.py runserver
    ```
    Visit `http://127.0.0.1:8000/` for the public site, or
    `http://127.0.0.1:8000/accounts/login/` to log in as any seeded role
    and reach your role-specific dashboard at `/dashboard/`.

## ⚠️ Breaking Change: Custom User Model

This phase introduces `accounts.User` as `AUTH_USER_MODEL`. Django does
not support switching to a custom user model once migrations have been
applied against the default one — so if you previously ran `migrate` on
this project (Phases 1–3), **you must drop and recreate your local
database** before running `migrate` again. This is a one-time step; there
is no real production data to lose at this stage (only seeded/test data).

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
| `ENQUIRY_EDIT_WINDOW_MINUTES` | Minutes after submission a student may self-edit their enquiry (default `30`) |
| `CORRECTION_REQUEST_EXTENDS_EDIT_WINDOW` | Whether an open staff Correction Request lets a student edit past an otherwise-expired window (default `True`) |

## Usage

- **Students** browse Colleges → College Details → Courses on the public
  site, with or without an account, and can submit an **Admission Enquiry**
  directly from any course's "Enquire Now" button — no account required.
  They can also register/log in for a personal dashboard
  (`/dashboard/student/`); enquiries submitted while logged in are
  automatically linked to their account.
- **College Admins** log in to manage their own college's staff
  (`/dashboard/college/staff/`), browse their college's enquiries
  (`/dashboard/enquiries/`) and view individual enquiry details
  (`/dashboard/enquiries/<id>/`) — strictly scoped to their own college.
- **College Staff** log in to view their college's dashboard and its
  enquiries (same `/dashboard/enquiries/` listing, scoped to their own
  college; staff management is Admin-only).
- **Platform Admin** logs in to `/dashboard/platform/` to approve/reject/
  suspend colleges, see platform-wide stats, and browse **every**
  college's enquiries via the same `/dashboard/enquiries/` listing.

Search/filter/sort (Phase 6), edit (Phase 7), and delete/restore
(Phase 8) are all live at `/dashboard/enquiries/` and its Recycle Bin.

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
- [x] Phase 3: Home/About/Courses/Contact routes all return 200; Courses
      page correctly lists only active courses (5 of 6 seeded, excluding
      the inactive Diploma); Contact form rejects invalid input (6 inline
      errors shown) and accepts valid input (302 redirect, success message
      shown, submission logged); accessibility verified (all 5 form fields
      have associated `<label for>`, error messages carry `role="alert"`)
- [x] Multi-college refactor: `College`/`Course`/`Enquiry` relationships
      verified (zero `enquiry.college` / `course.college` mismatches across
      9 seeded enquiries); per-college course-name uniqueness confirmed in
      both directions (same name allowed at a different college, rejected
      at the same college); `Colleges`/`College Detail`/grouped `Courses`
      pages all verified; search and state-filter verified
- [x] Authentication & RBAC foundation: custom `AUTH_USER_MODEL` migrates
      cleanly from scratch; login/logout/student-registration verified;
      role-based `403`s verified for every cross-role attempt (College
      Admin → Platform Dashboard, College Staff → Manage Staff, Student →
      Platform Dashboard); **college-ownership isolation verified** — a
      College Admin can only ever create staff for, or view data from,
      their own college (tested by attempting to add staff "for" another
      college and confirming the created account was scoped to the
      *actor's* college regardless); `seed_data` idempotency re-confirmed
      after the rewrite
- [x] Phase 4: Admission Enquiry submission verified end-to-end via
      Django's test client — GET the enquiry form for a live course
      (200); valid POST creates an `Enquiry` with `college` correctly
      auto-derived from the course's college, then redirects (302) to a
      working confirmation page (200); invalid POST (bad mobile number)
      re-renders the form with errors (200) and creates no record;
      enquiry URLs for an inactive course or a nonexistent course both
      correctly return 404; Home/Colleges/College Detail/Courses/Contact
      re-verified with no regressions
- [x] Phase 5: Enquiry Management verified end-to-end via Django's test
      client for all 3 staff roles — Platform Admin sees every enquiry
      (count cross-checked against the DB total, 200); College Admin/Staff
      see only their own college's enquiries (count cross-checked, 200);
      cross-college detail access correctly 404s (ownership isolation);
      own-college detail access returns 200 with correct data; Student
      role correctly blocked (403); anonymous correctly redirected to
      login (302); pagination verified with 25 bulk-created records
      (page 1/2 both 200, out-of-range and below-range page numbers both
      clamp to 200 instead of erroring — this caught and fixed a real
      `EmptyPage` bug in the initial pagination template); all previously
      working public and dashboard routes re-verified with no regressions
- [x] Phase 6: Search, Filter & Sorting verified end-to-end via Django's
      test client — search matched correctly on student name, email and
      college name substrings (results cross-checked against expected
      matches); college filter, course filter, gender filter, status
      filter and admission-year filter each verified independently
      (every returned row confirmed to match the filter); combined
      filters correctly AND together; sort verified in both directions
      for student name, college, course and submission date (result
      order cross-checked against Python's own `sorted()`); a malformed
      querystring (`admission_year=notanumber&sort=bogus&dir=bogus&
      gender=Z&status=BOGUS`) degrades to "no filter" instead of
      erroring (200, full unfiltered count); pagination combined with an
      active filter preserves that filter across pages (verified with
      25 bulk-created records, second-page results still 100% matching
      the filter, and the page-2 querystring correctly excludes `page`
      but keeps the filter); College Admin's filter form was confirmed
      to have no `college` field at all, and injecting a `?college=`
      query param for another college was confirmed to have zero effect
      (still scoped to their own college — ownership rule holds);
      Phase 4/Phase 5 regression-checked with no breakage (own-college
      detail 200, cross-college detail 404, Student 403, anonymous 302,
      Home/Colleges routes 200)
- [x] Phase 7: Update Module verified end-to-end via Django's test client
      — Platform Admin's edit form confirmed to have an enabled `college`
      field pre-selected to the enquiry's current college; College
      Admin/Staff's form confirmed to have `college` restricted to just
      their own college **and** `disabled`; a valid edit (name, status,
      staff notes) confirmed to persist and redirect to the detail page
      with a success message; reassigning an enquiry to a course in a
      genuinely different college (Platform Admin) confirmed to update
      both `course` and the auto-derived `college` together; submitting a
      college/course pair that don't actually match confirmed to
      redisplay the form with a field-level error and leave the database
      record unchanged; an out-of-range value (percentage > 100)
      confirmed to redisplay with a field-level error; a College
      Admin's attempt to inject a different college via a hand-crafted
      POST body confirmed to have **zero effect** (disabled field, server
      ignores submitted value); a College Admin's attempt to select
      another college's course (outside their restricted queryset)
      confirmed to be rejected as an invalid choice; cross-college edit
      access confirmed to 404 on both GET and POST (verified with a
      valid CSRF token, so the 404 is the view's own ownership check, not
      just CSRF rejection); Student (403) and anonymous (302) both
      re-confirmed blocked; Phase 4/5/6 regression pass (public routes,
      enquiry list + search, enquiry detail) all still 200
- [x] Phase 8: Delete & Restore verified end-to-end via Django's test
      client — a GET to the delete URL confirmed to be a no-op (no state
      change, matching the approve/reject/suspend-college convention
      already used elsewhere in this app); a POST soft-deletes (flips
      `is_deleted`) and immediately disappears from the active list and
      404s on its own detail page (confirming `Enquiry.objects`, the
      default manager, already excludes it); the same record confirmed
      to appear in the Recycle Bin (`Enquiry.all_objects`); Restore
      confirmed to flip it back and make the detail page reachable again;
      **two-step safety** confirmed directly — attempting to
      permanently-delete a record that is *not yet* in the Recycle Bin
      returns 404 (the row is untouched), and only after soft-deleting it
      first does permanent deletion succeed and the row actually vanish
      from `Enquiry.all_objects`; College Staff confirmed able to
      soft-delete and restore but blocked (403, both GET and POST) from
      permanent deletion, and the Recycle Bin template's
      `can_permanently_delete` flag confirmed `False` for that role so
      the button isn't even rendered; College Admin confirmed able to
      permanently delete within their own college; cross-college
      isolation re-verified for all three new actions (soft-delete,
      restore, permanent-delete each 404 on another college's enquiry,
      leaving it completely untouched); Student (403) and anonymous
      (302) both re-confirmed blocked from the Recycle Bin; full
      Phase 4–7 regression pass (public routes, enquiry list, sort,
      enquiry edit) all still 200
- [x] Phase 9: Authentication & Authorization — **verification pass**,
      no code changes (already fully implemented in the Platform
      Refactor). Verified via Django's test client: login with correct
      credentials authenticates and redirects to the role-appropriate
      dashboard; login with a wrong password redisplays the form with a
      non-field error and does not authenticate; logout (POST, matching
      the actual navbar form — Django 5.x's `LogoutView` is POST-only)
      clears the session; every one of the 7 management URLs tested
      (`/dashboard/`, `/dashboard/platform/`, `/dashboard/college/`,
      `/dashboard/college/staff/`, `/dashboard/student/`,
      `/dashboard/enquiries/`, `/dashboard/enquiries/recycle-bin/`)
      redirects an anonymous visitor to `/accounts/login/?next=<url>`;
      logging in via that link lands back on the originally-requested
      page, not just the dashboard root; a Student and (separately)
      College Staff each hitting every page outside their role
      (platform dashboard, college dashboard, manage-staff,
      enquiry list, recycle bin, permanent-delete) get a real **403**,
      not a silent redirect or 200; the correct role for each of those
      pages gets **200**; `dashboard_home` routes all 4 roles to the
      right landing page; public pages (Home, About, Colleges, Courses,
      Contact, Login, Register) remain reachable without authentication,
      confirming the intentionally-public Version 1.0 scope wasn't
      accidentally locked down; CSRF protection confirmed active on the
      login form itself (POST without a token → 403)
- [x] Phase 10: Dashboard verified end-to-end — both dashboards render
      (200) with all Phase 10 context keys present; **analytics accuracy
      independently verified** against ground truth computed directly
      with Python's `collections.Counter` (not by re-reading the view's
      own logic) for both the college-wise chart (every college
      represented, including zero-count ones, all counts matching) and
      the status-wise chart at both platform-wide and single-college
      scope (all 8 statuses represented, all counts matching, and the
      status chart's total independently confirmed to equal the
      dashboard's own enquiry-count stat); Recent Enquiries confirmed to
      show at most 10 rows, newest-first, matching the exact top-10 by
      `created_at`; the `json_script`-embedded chart data confirmed to
      parse as valid JSON straight out of the rendered HTML; the
      **empty-state path** directly verified with a freshly-created
      college that has zero enquiries — no `<canvas>` rendered and
      Chart.js's CDN script not even requested, only the empty-state
      message, with no server error; College Staff confirmed to see the
      same status chart as College Admin, while "Manage Staff" correctly
      stays admin-only (regression); Student (403) and anonymous (302)
      re-confirmed blocked from both dashboards; full Phase 4–9
      regression pass (public routes, enquiry list, sort, edit, recycle
      bin) all still 200. One bug was found and fixed during this
      phase's own testing: a JS comment containing a literal `{{ }}`
      inside a `<script>` block was being parsed by the Django template
      engine as an (invalid) empty variable tag, causing a 500 on both
      dashboards — see CHANGELOG.md.
- [x] Admin Panel Upgrade: verified end-to-end via Django's test client
      against a full RBAC matrix. **Login**: College Admin authenticates
      and reaches the admin index; College Staff's admin-login attempt
      is rejected by Django's own `AdminAuthenticationForm` (is_staff
      required) before it even reaches our custom logic; Student and
      anonymous both redirected. **Branding**: "Campora Administration
      Panel" present, "Django administration" absent, custom CSS linked,
      footer present — confirmed on both the index and the login page
      (which inherits the same base_site.html). **Platform Admin**:
      confirmed 200 on every changelist (College, Course, Enquiry, User,
      StaffProfile, StudentProfile, Group, LogEntry); confirmed to see
      colleges and enquiries from every college. **College Admin
      isolation** (two distinct seeded colleges, A and B): confirmed
      College Admin A's changelists (College, Course, Enquiry,
      StaffProfile) show 100% of their own college's rows and 0% of
      college B's; confirmed the app-list hides User/Group/
      StudentProfile entirely. **Object-level enforcement** (not just
      list-hiding): confirmed College Admin A hitting college B's
      Course/Enquiry/College change-page URLs directly by guessed PK are
      all denied (not 200); confirmed a direct hit on the User
      changelist is a real 403. **College cannot be added/deleted by
      College Admin** (403 on both), **but can view/edit their own**
      (200) — lifecycle stays owned by the existing approval workflow.
      **Course add/edit**: confirmed College Admin A can create a course
      in their own college; confirmed a crafted POST attempting to
      inject college B's id is rejected (form validation, not silently
      accepted) and no row is created. **Enquiry admin**: confirmed the
      pre-existing `all_objects` (Recycle-Bin-aware) visibility is
      unchanged — a soft-deleted enquiry is still visible to Platform
      Admin and to its own college's Admin in the admin panel. **Dropdown
      scoping**: confirmed via the actual `/admin/autocomplete/` endpoint
      (the real enforcement point for `autocomplete_fields`, since
      Select2 widgets don't embed options server-side) that College
      Admin A's College-field autocomplete returns only their own
      college. **Admin dashboard**: confirmed Platform Admin sees Total
      Colleges/Latest Admissions/Recent Activity/System Status/Quick
      Links; confirmed College Admin's version is correctly scoped
      (their own college's name in the heading, no Total Colleges card,
      no System Status section). **Audit Logs**: confirmed genuinely
      read-only — GET renders a view-only page (no Save button, no
      editable `<input>`s beyond the nav search box) and a direct POST
      attempt to change a `LogEntry` is rejected (403) with the row
      unchanged; confirmed College Admin is denied (403) entirely.
      **Quick Actions**: confirmed all 8 Platform / 6 College Admin cards
      render with correct links (`#analytics` anchor, `/admin/...`
      changelist URLs via `{% url %}`, existing dashboard pages); Reports
      and Platform Settings confirmed rendered as disabled
      "Coming Soon" cards, not dead links; confirmed College Staff sees
      only the two non-admin cards (Admission Enquiries, College
      Analytics) with every admin-linked/admin-only card hidden.
      **Full regression**: every public route, both dashboards, enquiry
      list/search/sort/detail/edit/recycle-bin (Phases 4–10) re-verified
      at their expected status codes — no regressions.
- [ ] CSV export — not yet built (future phase)

## Future Enhancements

SMS notifications, document uploads, advanced reporting (see `PROJECT_BRAIN.docx`).

## Contributors

Add team member names here.

## License

Educational / College Project.
