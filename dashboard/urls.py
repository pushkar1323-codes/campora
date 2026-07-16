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
    path("enquiries/<int:pk>/", views.enquiry_detail, name="enquiry_detail"),
    path("student/", views.student_dashboard, name="student"),
]
