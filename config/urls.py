"""
URL configuration for Campora – College Admission & Student Enquiry Portal.

Per SYSTEM_ARCHITECTURE.docx section 3, each app owns its own URL namespace.
Apps are wired in here as they are implemented, phase by phase.

/admin/ serves the custom Campora Administration Panel (core.admin_site.
campora_admin_site), not Django's default admin.site — see that module's
docstring for the full rationale (role-based access control replacing
is_staff/permission-group checks, multi-college data isolation). The
default admin.site is intentionally never registered into or wired up
anywhere in this project, to avoid two competing admin interfaces. Each
app's own admin.py already registers its models onto campora_admin_site
(via @admin.register(Model, site=campora_admin_site)); those modules are
imported automatically by Django's own admin autodiscovery
(django.contrib.admin.apps.AdminConfig.ready()) at startup, same as it
always has been — nothing extra is needed here for that.
"""
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from core.admin_site import campora_admin_site

urlpatterns = [
    path('admin/', campora_admin_site.urls),
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('admissions/', include('admissions.urls')),
    # courses URLs are wired in a later phase (Phase 12 - staff-side course
    # CRUD) as that app's own views are implemented (see IMPLEMENTATION_PLAN.docx).
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
