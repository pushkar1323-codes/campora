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

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .decorators import role_required
from .forms import StudentBasicInfoForm, StudentProfileEditForm, StudentSignUpForm
from .models import StudentProfile, User

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


@role_required(User.Role.STUDENT)
def profile_view(request):
    """Phase 1, Feature 1/2 — a Student views and edits their own profile.

    Restricted to the STUDENT role and always bound to `request.user` —
    there is no user-id parameter in the URL or the form, so there is no
    way to reach or edit anyone else's profile through this view (Feature
    2: "Student can edit own profile" / "cannot edit another student's
    profile"). College Staff/Admin get read-only visibility into a
    student's submitted personal information via the enquiry detail page
    instead (Feature 3) — not through this view, which they can't reach
    at all (@role_required(STUDENT) excludes them). Platform Admin's
    "may edit when absolutely necessary" override is already covered by
    the existing Campora Admin Panel's Platform-Admin-only StudentProfile
    registration — see accounts/admin.py.

    `get_or_create` defensively covers any account created before this
    phase that might somehow lack a StudentProfile row.
    """
    profile, _ = StudentProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        user_form = StudentBasicInfoForm(request.POST, instance=request.user)
        profile_form = StudentProfileEditForm(request.POST, instance=profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            logger.info("Student profile updated: %s", request.user.username)
            messages.success(request, "Your profile has been updated.")
            return redirect("accounts:profile")
        messages.error(request, "Please correct the errors below and try again.")
    else:
        user_form = StudentBasicInfoForm(instance=request.user)
        profile_form = StudentProfileEditForm(instance=profile)

    return render(
        request,
        "accounts/profile.html",
        {"user_form": user_form, "profile_form": profile_form},
    )
