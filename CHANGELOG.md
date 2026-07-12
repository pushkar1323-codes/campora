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
