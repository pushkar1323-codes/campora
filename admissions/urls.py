from django.urls import path

from . import views

app_name = "admissions"

urlpatterns = [
    path("courses/<int:course_id>/enquire/", views.enquiry_create, name="enquiry_create"),
    path("enquiry/<int:pk>/success/", views.enquiry_success, name="enquiry_success"),
]
