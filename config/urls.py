"""
URL configuration for Campora – College Admission & Student Enquiry Portal.

Per SYSTEM_ARCHITECTURE.docx section 3, each app owns its own URL namespace.
Apps are wired in here as they are implemented, phase by phase.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Campora admin branding (staff-facing; does not affect app/package names).
admin.site.site_header = "Campora Administration"
admin.site.site_title = "Campora Admin"
admin.site.index_title = "Welcome to Campora Administration"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    # accounts, admissions, courses, dashboard URLs are wired in later phases
    # as those apps are implemented (see IMPLEMENTATION_PLAN.docx).
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
