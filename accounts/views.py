"""
Authentication views for Campora.

Login/logout use Django's built-in class-based auth views (battle-tested,
handles CSRF/session correctly out of the box) with Campora-branded
templates. Only student self-registration is implemented here — College
Admin/Staff accounts are provisioned via the dashboard app (see
dashboard/views.py::manage_staff), not self-registered, per the platform's
role hierarchy.
"""
import logging

from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .forms import StudentSignUpForm

logger = logging.getLogger(__name__)


class CamporaLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


def register_student(request):
    """Self-service student registration. Logs the new student in
    immediately on success (no email verification — out of scope)."""
    if request.user.is_authenticated:
        return redirect("dashboard:home")

    if request.method == "POST":
        form = StudentSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            logger.info("New student registered: %s", user.username)
            return redirect("dashboard:home")
    else:
        form = StudentSignUpForm()

    return render(request, "accounts/register.html", {"form": form})
