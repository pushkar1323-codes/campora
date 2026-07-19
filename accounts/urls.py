from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.CamporaLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="core:home"), name="logout"),
    path("register/", views.register_student, name="register"),
    path("profile/", views.profile_view, name="profile"),
]
