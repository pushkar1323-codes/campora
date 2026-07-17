from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_home, name="home"),
    path("platform/", views.platform_dashboard, name="platform"),
    path("platform/colleges/<int:pk>/approve/", views.approve_college, name="approve_college"),
    path("platform/colleges/<int:pk>/reject/", views.reject_college, name="reject_college"),
    path("platform/colleges/<int:pk>/suspend/", views.suspend_college, name="suspend_college"),
    path("college/", views.college_dashboard, name="college"),
    path("college/staff/", views.manage_staff, name="manage_staff"),
    path("enquiries/", views.enquiry_list, name="enquiry_list"),
    path("enquiries/recycle-bin/", views.enquiry_recycle_bin, name="enquiry_recycle_bin"),
    path("enquiries/<int:pk>/", views.enquiry_detail, name="enquiry_detail"),
    path("enquiries/<int:pk>/edit/", views.enquiry_edit, name="enquiry_edit"),
    path("enquiries/<int:pk>/delete/", views.enquiry_delete, name="enquiry_delete"),
    path("enquiries/<int:pk>/restore/", views.enquiry_restore, name="enquiry_restore"),
    path(
        "enquiries/<int:pk>/permanent-delete/",
        views.enquiry_permanent_delete,
        name="enquiry_permanent_delete",
    ),
    path("student/", views.student_dashboard, name="student"),
]
