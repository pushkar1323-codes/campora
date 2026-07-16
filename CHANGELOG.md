# Changelog

All notable changes to this project are documented in this file, organized by
implementation phase (see `IMPLEMENTATION_PLAN.docx`).

## [0.1.0] - Phase 1: Project Setup

### Added
- Django project (`config`) initialized with 5 apps: `core`, `accounts`,
  `admissions`, `courses`, `dashboard`
- Bootstrap 5 (via CDN) integrated into a base template with sticky navbar,
  footer, and Django messages rendered as dismissible Bootstrap alerts
- `templates/`, `static/` (`css`, `js`, `images`), and `media/` directories
  configured
- Local MySQL database configured via `mysqlclient` and environment
  variables (`python-decouple`), matching `DATABASE_DESIGN.docx`
- Placeholder public routes and views: Home, About, Courses, Contact
  (full content scheduled for Phase 3)
- `requirements.txt`, `.env.example`, `.gitignore`
- Git repository initialized with an initial commit

### Notes
- No models/migrations yet — that is Phase 2 (Database Design)
- Public pages currently render placeholder content only

### Fixed (post-Phase 1)
- Pinned `Django==5.2.8` (LTS) instead of `6.0.x` in `requirements.txt`.
  Django 6.0 requires Python 3.12+; 5.2 LTS supports Python 3.10–3.14 and is
  the safer, longer-supported choice for this project. Re-verified
  `manage.py check` and all routes after the change — no issues.

### Branding (post-Phase 1)
- Applied official **Campora** branding to all Phase 1 user-facing
  elements: browser title, meta description, navbar (logo + tagline +
  "Apply Now" CTA), footer (quick links, developer credit, copyright),
  page titles, Django admin site header/title, and `README.md`.
- Introduced the Campora design system in `static/css/style.css`: color
  palette (primary #2563EB, accent #10B981, background #F8FAFC, text
  #1F2937), Poppins (headings) + Inter (body) via Google Fonts, Lucide
  icons via CDN, rounded buttons/cards with soft shadows, and a reusable
  empty-state style for future dashboard phases.
- No renames: `college_admission` project folder, Django apps (`core`,
  `accounts`, `admissions`, `courses`, `dashboard`), database name
  (`college_admission_db`), URLs, and folder structure are all unchanged.
- Re-verified `manage.py check` and all routes (`/`, `/about/`,
  `/courses/`, `/contact/`, `/admin/`) after rebranding — no issues.

## [0.2.0] - Phase 2: Database Design

### Added
- `Course` model (`courses` app): name, duration, eligibility, description,
  active flag, timestamps
- `Enquiry` model (`admissions` app): full student/academic detail set per
  `DATABASE_DESIGN.docx`, FK to `Course` (`on_delete=PROTECT` — a course
  with existing enquiries cannot be deleted, only deactivated), `TextChoices`
  for gender and the 8-stage admission workflow status, soft-delete support
- Custom `EnquiryManager`/`EnquiryQuerySet`: `Enquiry.objects` excludes
  soft-deleted rows by default; `Enquiry.all_objects` includes everything
  (used by the admin and, later, the Recycle Bin)
- Reusable validators in `admissions/validators.py`: mobile number format,
  DOB-not-future, admission-year-not-past — shared by the model layer now
  and by Django Forms in Phase 4
- Database indexes on `email`, `mobile`, `admission_year`, `status`,
  `is_deleted`, plus composite indexes on `(status, admission_year)` and
  `(is_deleted, status)` for future filtered dashboard queries
- Initial migrations: `courses/migrations/0001_initial.py`,
  `admissions/migrations/0001_initial.py`
- Django admin registration for both models with search, filters, and
  soft-delete/restore actions
- `python manage.py seed_data` — idempotent sample data command (6 courses,
  9 enquiries spanning all workflow statuses, including one soft-deleted
  record to demonstrate the feature)

### Testing performed
- `manage.py check` — no issues
- `makemigrations --check --dry-run` — no undetected model changes
- Migrations applied cleanly against a test database
- `seed_data` run twice — confirmed idempotent (zero duplicates on rerun)
- Verified in the Django shell: soft-delete manager filtering, FK
  `select_related` resolution, and all three validators correctly reject
  invalid input
- Verified end-to-end via the Django admin: login, Course list (6 rows),
  Enquiry list (9 rows including the soft-deleted one)

### Notes
- No live MySQL server is available in the development sandbox used to
  build this phase; migrations/seed data were verified against SQLite as a
  substitute. The shipped configuration remains MySQL per
  `DATABASE_DESIGN.docx` — run `python manage.py migrate` against your own
  local MySQL instance to apply these migrations there.

## [0.3.0] - Phase 3: Public Website

### Added
- **Home page**: hero banner, About preview, data-driven "Popular Courses"
  section (top 3 active courses), "Why Choose Campora" section, CTA banner
- **About page**: institute overview, mission, vision, values
- **Courses page**: full grid of active courses pulled live from the
  `Course` model (inactive courses correctly excluded)
- **Contact page**: address/phone/email/hours block + a validated general
  enquiry form (`core/forms.py::ContactForm`)
- Reusable `templates/partials/course_card.html` partial — shared by Home
  and Courses pages instead of duplicating card markup (DRY)
- `LOGGING` configuration in `settings.py`: console handler with a
  timestamped formatter, per-app loggers (`core`, `accounts`, `admissions`,
  `courses`, `dashboard`) configurable via `LOG_LEVEL`/`DJANGO_LOG_LEVEL`
  env vars

### Design decisions
- The Contact page's enquiry form is a plain `forms.Form`, not tied to a
  database table — `DATABASE_DESIGN.docx` does not define a table for
  general contact messages (only `Course` and `Enquiry`). The form is
  fully validated (server-side) and logs each submission; persisting it
  to a table can be added later if that becomes a real requirement. This
  is intentionally distinct from the course-specific **Admission Enquiry**
  form, which is backed by the `Enquiry` model and is built in Phase 4.
- Contact form submission uses the Post/Redirect/Get pattern (redirects to
  `/contact/` on success with a Django-messages confirmation) so a page
  refresh never resubmits the form.
- The public Courses page continues to live in the `core` app (as scaffolded
  in Phase 1's `core:courses` URL) rather than moving to the `courses` app,
  to avoid renaming an existing URL. The `courses` app still owns the
  `Course` model and will own the staff-side course CRUD UI in Phase 12.

### Testing performed
- `manage.py check` — no issues
- All 4 public routes (`/`, `/about/`, `/courses/`, `/contact/`) return `200`
- Courses page confirmed to render exactly 5 course cards (the 6th seeded
  course is `is_active=False` and is correctly excluded)
- Contact form: invalid submission (bad email, too-short message) returns
  `200` with 6 inline validation error blocks; valid submission returns
  `302` redirect, success message renders after redirect, and the
  submission is correctly written to the console log
- Accessibility: all 5 form fields have a `<label for>` correctly bound via
  `id_for_label`; validation errors carry `role="alert"`

## [0.4.0] - Platform Refactor: Multi-College Architecture + Authentication/RBAC

This is a major architectural refactor requested mid-project: Campora
moved from a single-college enquiry system to a multi-college SaaS
platform with role-based authentication. Completed as one combined pass
covering both the data-model refactor and the authentication foundation.

### Added — Multi-college data model
- `College` model (`courses` app): name, slug (auto-generated), logo,
  cover_image, short/full description, address/city/state, phone/email/
  website, and an approval-workflow `status` field (Pending / Approved /
  Rejected / Suspended). Only Approved colleges are ever shown publicly.
- `Course.college` FK (`on_delete=CASCADE`). Course-name uniqueness changed
  from **globally unique** to **unique per college** (two colleges can
  both offer "BBA") via a `UniqueConstraint`.
- `Enquiry.college` FK — **auto-derived** from `enquiry.course.college` on
  every save (`editable=False`, not independently settable), guaranteeing
  the two can never drift out of sync. `Enquiry.submitted_by` FK to `User`
  (nullable) links an enquiry to the logged-in student who submitted it,
  where applicable.

### Added — Authentication & role-based access control
- Custom user model `accounts.User` (`AUTH_USER_MODEL`) with a `role`
  field: **Platform Admin**, **College Admin**, **College Staff**,
  **Student**. One auth system, not four separate ones.
- `StudentProfile` / `StaffProfile` role-extension models. `StaffProfile`
  links a College Admin/Staff user to exactly one `College`.
- `accounts/decorators.py::role_required` — reusable view decorator
  enforcing login + role membership (403 on role mismatch).
- `accounts/decorators.py::get_staff_college` — the single source of truth
  for "which college does this staff user belong to," used by every
  college-scoped view so ownership enforcement is consistent everywhere.
- Login (`/accounts/login/`), logout, and **student self-registration**
  (`/accounts/register/`). College Admin/Staff accounts are *provisioned*
  (by a Platform Admin or College Admin), not self-registered — no email
  verification/OTP/social login, per the explicit scope exclusions.
- Role-scoped dashboards (`dashboard` app):
  - **Platform Dashboard** (`/dashboard/platform/`): platform-wide stats +
    a college approval queue (approve/reject/suspend actions).
  - **College Dashboard** (`/dashboard/college/`): stats and recent
    enquiries, strictly scoped to the logged-in staff member's own college.
  - **Manage Staff** (`/dashboard/college/staff/`, College Admin only):
    add/list College Staff for their own college — the college is always
    derived from the requesting admin's own `StaffProfile`, never taken
    from form input, which is what makes "college ownership" actually
    enforced rather than merely advisory.
  - **Student Dashboard** (`/dashboard/student/`): profile summary; an
    honest placeholder for enquiry tracking (the admission-enquiry
    *submission* form itself is still Phase 4, not built yet, so there is
    nothing real to track against for a logged-in student today).

### Changed — Public website (multi-college)
- **Home**: "Featured Courses" replaced with "Featured Colleges" +
  platform-wide stats (college/course counts) + a college search bar in
  the hero.
- **New: Colleges directory** (`/colleges/`) — searchable (name/city/
  state) and filterable (by state) grid of approved colleges.
- **New: College Detail** (`/colleges/<slug>/`) — cover image, logo,
  description, contact info, active courses, an honest "gallery coming
  soon" placeholder, and at-a-glance stats.
- **Courses** (`/courses/`) — now grouped by college via Django's
  `{% regroup %}` tag instead of a flat list.
- **About** / **Contact** — copy updated for the platform framing;
  Contact is explicitly platform-level, with a pointer to each college's
  own Detail page for college-specific contact info.
- Navbar/footer: added a "Colleges" link and auth-aware Login/Sign Up vs.
  Dashboard/Log Out controls.

### Security decision worth flagging
- College Admin/Staff accounts are deliberately **not** granted Django's
  `is_staff=True` (no `/admin/` access). Django's built-in admin is not
  scoped per-college, so granting it would let a College Admin see every
  college's data there — directly contradicting "College Staff must never
  access another college's data." They use the college-scoped `dashboard`
  app instead. (Caught and fixed during this pass — an earlier draft of
  both `seed_data` and `StaffCreationForm` set `is_staff=True`.)

### ⚠️ Breaking change: fresh migrations required
- Adopting a custom `AUTH_USER_MODEL` requires a clean migration history
  for auth-related tables — Django does not support this on top of an
  already-`migrate`d default `auth.User` table. Old `courses` and
  `admissions` initial migrations were deleted and regenerated fresh
  alongside the new `accounts` initial migration. **Anyone who previously
  ran `migrate` on this project (Phases 1–3) must drop and recreate their
  local database** before migrating again — see the README's "Breaking
  Change" note. This affects only local dev/seeded data; there is no real
  production data at this stage.

### Testing performed
- `manage.py check` and `makemigrations --check --dry-run` — clean
- Fresh `migrate` verified end-to-end against SQLite (all 3 apps'
  migrations apply in correct dependency order)
- `seed_data` rewritten and re-verified idempotent; confirmed zero
  `enquiry.college` / `course.college` mismatches across all 9 seeded
  enquiries; confirmed per-college course-name uniqueness in both
  directions (allowed across colleges, rejected within the same college)
- Full RBAC matrix tested via login + route access for all 4 roles:
  Platform Admin (`200` on platform dashboard), College Admin (`403` on
  platform dashboard, `200` on their own college dashboard), College Staff
  (`403` on Manage Staff, which is Admin-only), Student (`403` on platform
  dashboard, `200` on student dashboard)
- **College-ownership isolation** specifically verified: logged in as one
  college's admin and confirmed their dashboard/staff list only ever shows
  their own college; used Django's test client to confirm that a staff
  member created via the Manage Staff form is always scoped to the
  *submitting* admin's college, never a different one
- Student self-registration verified end-to-end (form submission → user +
  StudentProfile created → auto-login → redirect to student dashboard)

## [0.5.0] - Phase 4: Admission Enquiry

Implements the actual student-facing admission enquiry submission
workflow, on top of the multi-college architecture landed in the
Platform Refactor. The `Enquiry` model, validators and soft-delete
manager already existed (Phase 2 / Platform Refactor); this phase adds
the missing views, form, URLs, and templates that let a student actually
submit one.

### Added
- `admissions/forms.py::EnquiryForm` — a `ModelForm` bound to a *specific*
  `Course` instance passed in by the view (`course=` kwarg), not a form
  field. There is no College or Course dropdown on the form at all: the
  student always arrives here from a specific college's course card, so
  the course (and, by extension, its college) is fixed by the URL —
  satisfying MASTER_RULES.docx section 6 ("Validation must prevent
  selecting a Course that does not belong to the chosen College") by
  construction rather than by a second runtime check. `Enquiry.college` is
  still auto-derived from `course.college` in `Enquiry.save()` as before.
- `admissions/views.py`:
  - `enquiry_create(request, course_id)` — looks up the course, scoped to
    `is_active=True` and `college__status=APPROVED` (404 otherwise, so a
    guessed URL can't be used to enquire against an inactive course or an
    unapproved/suspended college). Renders/validates `EnquiryForm`; on
    success, auto-links `submitted_by` if a Student is logged in (never
    required — anonymous submission remains supported per
    SYSTEM_ARCHITECTURE.docx section 6); uses Post/Redirect/Get.
  - `enquiry_success(request, pk)` — confirmation page.
- `admissions/urls.py` (new): `courses/<int:course_id>/enquire/` and
  `enquiry/<int:pk>/success/`, wired into `config/urls.py` under
  `/admissions/`.
- `templates/admissions/enquiry_form.html` — Bootstrap 5 form; shows the
  fixed course + college as read-only context at the top (with a "Change
  Course" link back to the College Detail page), followed by the student's
  personal/academic details.
- `templates/admissions/enquiry_success.html` — confirmation page with a
  reference number, college/course/status summary, and next-step links.

### Changed
- `templates/partials/course_card.html` — the "Enquire Now" button now
  links to `admissions:enquiry_create` for that specific course, replacing
  the Phase 1-3 placeholder link to the generic Contact page. This card is
  shared by both the College Detail page and the public Courses page, so
  both surfaces are updated in one place.
- `config/urls.py` — added `path('admissions/', include('admissions.urls'))`.

### Testing performed
- `manage.py check` — clean.
- Fresh SQLite migrate + `seed_data`, then exercised the full flow via
  Django's test client:
  - GET the enquiry form for a real, active course — `200`.
  - Valid POST — `302` redirect to the success page; created `Enquiry` row
    confirmed to have `college_id == course.college_id` (auto-derivation
    still holds); success page — `200`.
  - Invalid POST (malformed mobile number) — form re-rendered with `200`
    and validation errors; confirmed no `Enquiry` row was created.
  - GET on an inactive course's enquiry URL — `404`.
  - GET on a nonexistent course id — `404`.
  - Re-verified Home, Colleges, College Detail, Courses and Contact pages
    all still return `200` after the course-card link change (no
    regression from the Platform Refactor).

## [0.6.0] - Phase 5: Enquiry Management

Adds the staff-facing enquiry management module — a professional listing
and detail view for the `Enquiry` records that Phase 4 lets students
submit. Lives inside the existing `dashboard` app (not a new app), reusing
its role-scoping and college-ownership patterns.

Scope note: per PROMPTS_PART_1.docx, Phase 5 covers listing, detail,
pagination, and displaying College/Course on every row. Live search,
filter and sort (by student/college/course/gender/status/admission year)
is its own separate phase (PROMPTS_PART_2.docx, Phase 6) and is
deliberately **not** included here, to avoid conflicting with that phase's
spec. The listing view is structured (proper `select_related`, indexed
model fields already in place) so Phase 6 can add filtering without
restructuring this view.

### Added
- `dashboard/views.py`:
  - `enquiry_list(request)` — `role_required(SUPER_ADMIN, COLLEGE_ADMIN,
    COLLEGE_STAFF)`. Platform Admin sees every enquiry; College
    Admin/Staff see only their own college's enquiries, scoped via the
    existing `get_staff_college(request.user)` helper (never a college id
    taken from the URL/query string). Paginated 20/page via Django's
    `Paginator`.
  - `enquiry_detail(request, pk)` — same role gate; a College Admin/Staff
    user gets a `404` (not `403`) for another college's enquiry, so a
    guessed URL can't even confirm the enquiry exists elsewhere. Platform
    Admin can view any (non-deleted) enquiry.
- `dashboard/urls.py` — `enquiries/` and `enquiries/<int:pk>/`.
- `templates/dashboard/enquiry_list.html` — table with Reference #,
  Student Name, Email, Mobile, College (shown only for the Platform
  Admin's all-colleges view — implicit and omitted for a college-scoped
  user), Course, Status badge, Submitted date, and a View action.
  Bootstrap 5 pagination controls, `?page=` preserved.
- `templates/dashboard/enquiry_detail.html` — full applicant + academic
  details, College/Course, status, internal staff notes (if any),
  timestamps, and whether the enquiry came from a logged-in student or a
  guest.

### Changed
- `templates/dashboard/college_dashboard.html` — added a "View All
  Enquiries" button next to the existing "Manage Staff" button; each row
  in the existing "Recent Enquiries" preview now links to the new detail
  page; added a "View All →" link above that preview table.
- `templates/dashboard/platform_dashboard.html` — added a "View All
  Enquiries" button in the header.
- `dashboard/views.py::student_dashboard` — corrected a stale docstring
  left over from before Phase 4 (it previously said the enquiry
  submission form "doesn't exist yet," which is no longer true).

### Bug fixed during testing
- The pagination template initially called
  `page_obj.previous_page_number` / `next_page_number` unconditionally
  (only gating the CSS `disabled` class on `has_previous`/`has_next`),
  which raises `EmptyPage` on the first/last page and 500'd the view.
  Fixed by only rendering those template variables inside their matching
  `{% if page_obj.has_previous %}` / `{% if page_obj.has_next %}` blocks.

### Testing performed
- `manage.py check` — clean.
- Fresh SQLite migrate + `seed_data`, then via Django's test client:
  - Platform Admin: listing shows every enquiry (count cross-checked
    against `Enquiry.objects.count()`) — `200`.
  - College Admin: listing count cross-checked against
    `Enquiry.objects.filter(college=own_college).count()` — `200`;
    detail view on their own enquiry — `200`; detail view on another
    college's enquiry — `404` (ownership isolation holds).
  - College Staff: listing — `200`.
  - Student: listing — `403` (blocked, as intended — enquiry management
    is staff-only).
  - Anonymous: listing — `302` redirect to login.
  - Pagination: bulk-created 25 extra enquiries for one college to force
    a second page; page 1 and page 2 both `200`; out-of-range
    (`?page=999`) and below-range (`?page=0`) both clamp cleanly to
    `200` instead of erroring (this is what caught the pagination bug
    above).
  - Re-verified Home/Colleges/College Detail/Courses/Contact and both
    existing dashboards all still return `200` — no regressions.

## [0.7.0] - Phase 6: Search, Filter & Sorting

### Added
- `dashboard/forms.py` (new file): `EnquiryFilterForm`, a plain (non-Model)
  `Form` bound to `request.GET`, used by `dashboard/views.py::enquiry_list`
  to search, filter and sort the Phase 5 enquiry listing.
  - Fields: `q` (search), `college` (Platform Admin only), `course`,
    `gender`, `status`, `admission_year`, `sort`, `dir`.
  - **College ownership carries through to filtering**: when instantiated
    with `staff_college=<their college>`, the `college` field is dropped
    entirely from the form (a College Admin/Staff user's scope is always
    decided server-side, never via the querystring) and the `course`
    field's choices are restricted to that college's own courses only.
  - **Fails safe on bad input**: every field is optional, and this form is
    deliberately read via `cleaned_data.get(...)` rather than gated on
    `is_valid()`, so one malformed query param (e.g. `admission_year=abc`)
    never breaks the whole page — it's simply ignored for that field only,
    per Django's normal per-field cleaning behaviour.
- `dashboard/views.py::enquiry_list` extended (same view, same URL, no
  breaking change to Phase 5):
  - **Search** (`q`): case-insensitive substring match, OR'd across
    student name, mobile, email, college name and course name.
  - **Filters**: college (Platform Admin only — a College Admin/Staff
    user's own-college scoping from Phase 5 is untouched), course,
    gender, status, admission year. All filters AND together with each
    other and with search.
  - **Sort**: student name / college / course / submission date, either
    direction via `sort`/`dir` query params. Defaults to submission date,
    newest first (matching the pre-Phase-6 default ordering), so an
    unfiltered/unsorted visit to the page looks identical to before.
  - **Pagination preserved**: the current querystring (minus `page`) is
    built once and reused for every pagination link and every sortable
    column-header link, so navigating pages or re-sorting never silently
    drops an active search or filter.
- `templates/dashboard/enquiry_list.html`:
  - New filter/search bar (Bootstrap 5, `GET` form) above the results
    table — search box, College dropdown (Platform Admin view only),
    Course/Gender/Status dropdowns, Admission Year input, Search button,
    and a "clear filters" button shown only when a filter is active.
  - Student Name / College / Course / Submitted column headers are now
    sortable links with a Lucide chevron-up/chevron-down indicator on the
    currently active sort column.
  - Pagination links (Previous/page-numbers/Next) now append the
    preserved querystring so they no longer silently drop filters.
  - Empty state now distinguishes "no enquiries exist at all" (Phase 5
    behaviour, unchanged) from "no results match the current
    search/filters" (new — includes a clear-filters link).
  - Header subtitle now shows a "filtered" badge and the *filtered* count
    when any search/filter is active.

### Changed
- No changes to `dashboard/urls.py`, `admissions/*`, `courses/*`,
  `accounts/*`, or any Phase 1–5 template other than
  `enquiry_list.html` — this phase only extends the existing Phase 5
  listing view and its template.

### Testing performed
- `manage.py check` — clean; `makemigrations --check --dry-run` — no
  drift (this phase adds no models/migrations).
- Fresh SQLite migrate + `seed_data`, then via Django's test client:
  - Search verified independently for student name, email and college
    name substrings — every returned row cross-checked to actually
    contain the search term.
  - Each filter (college, course, gender, status, admission year)
    verified independently — every returned row cross-checked against
    the filter value; a combined filter (status + gender) correctly
    AND'd (returned the expected empty set for a combination with no
    matching seed data).
  - Sort verified in both directions for all 4 sortable fields —
    resulting order cross-checked against Python's own `sorted()`.
  - Malformed querystring
    (`admission_year=notanumber&sort=bogus&dir=bogus&gender=Z&status=BOGUS`)
    correctly falls back to the unfiltered, default-sorted listing (200,
    not a 500) — confirms the fails-safe design of `EnquiryFilterForm`.
  - Pagination + filter interaction: bulk-created 25 extra enquiries for
    one course to force a second filtered page; page 2 of the
    course-filtered results — 200, every row still matching the course
    filter, and the pagination querystring correctly carried `course=`
    while excluding the stale `page=`.
  - College Admin's filter form confirmed to have **no** `college` field
    at all (`'college' in form.fields` — `False`); injecting
    `?college=<another college's id>` via the querystring confirmed to
    have zero effect — results remained 100% scoped to their own college
    (the Phase 5 ownership rule holds under Phase 6's new filters).
  - Phase 4/Phase 5 regression pass: own-college detail (200),
    cross-college detail (404), Student role (403), anonymous (302),
    and Home/Colleges public routes (200) all re-verified with no
    breakage.
