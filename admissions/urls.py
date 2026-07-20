from django.urls import path

from . import views

app_name = "admissions"

urlpatterns = [
    path("courses/<int:course_id>/enquire/", views.enquiry_create, name="enquiry_create"),
    path("enquiry/<int:pk>/success/", views.enquiry_success, name="enquiry_success"),
    path("enquiry/<int:pk>/edit/", views.enquiry_self_edit, name="enquiry_self_edit"),
    path("enquiry/<int:pk>/messages/", views.enquiry_conversation, name="enquiry_conversation"),
    path("messages/<int:pk>/edit/", views.message_edit, name="message_edit"),
    path("messages/<int:pk>/delete/", views.message_delete, name="message_delete"),
]
