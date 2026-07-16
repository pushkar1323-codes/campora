"""
Role-scoped dashboard views for Campora.

Every view here enforces "college ownership": a College Admin/Staff user
only ever sees data for accounts.decorators.get_staff_college(request.user)
— never a college selected via URL or POST data — so there is no way for
one college's admin to view or manage another college's data.

Scope note: this is the dashboard *foundation* (role landing pages, college
approval, staff provisioning) — full analytics/charts/CSV export are a
later phase (Phase 10/11 in IMPLEMENTATION_PLAN.docx).
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import get_staff_college, role_required
from accounts.forms import StaffCreationForm
from accounts.models import User
from admissions.models import Enquiry
from courses.models import College, Course
from .forms import SORT_FIELD_MAP, EnquiryFilterForm

logger = logging.getLogger(__name__)


@login_required
def dashboard_home(request):
    """Single entry point (`/dashboard/`) that routes each user to the
    dashboard for their role."""
    user = request.user
    if user.role == User.Role.SUPER_ADMIN:
        return redirect("dashboard:platform")
    if user.role in (User.Role.COLLEGE_ADMIN, User.Role.COLLEGE_STAFF):
        return redirect("dashboard:college")
    if user.role == User.Role.STUDENT:
        return redirect("dashboard:student")
    return redirect("core:home")


@role_required(User.Role.SUPER_ADMIN)
def platform_dashboard(request):
    """Platform Admin: platform-wide stats + college approval queue."""
    stats = {
        "total_colleges": College.objects.count(),
        "approved_colleges": College.objects.filter(status=College.Status.APPROVED).count(),
        "pending_colleges": College.objects.filter(status=College.Status.PENDING).count(),
        "total_courses": Course.objects.count(),
        "total_enquiries": Enquiry.objects.count(),
        "total_students": User.objects.filter(role=User.Role.STUDENT).count(),
    }
    pending_colleges = College.objects.filter(status=College.Status.PENDING)
    all_colleges = College.objects.all()
    context = {"stats": stats, "pending_colleges": pending_colleges, "all_colleges": all_colleges}
    return render(request, "dashboard/platform_dashboard.html", context)


@role_required(User.Role.SUPER_ADMIN)
def approve_college(request, pk):
    if request.method == "POST":
        college = get_object_or_404(College, pk=pk)
        college.status = College.Status.APPROVED
        college.save(update_fields=["status", "updated_at"])
        logger.info("College approved by %s: %s", request.user.username, college.name)
        messages.success(request, f"{college.name} has been approved.")
    return redirect("dashboard:platform")


@role_required(User.Role.SUPER_ADMIN)
def reject_college(request, pk):
    if request.method == "POST":
        college = get_object_or_404(College, pk=pk)
        college.status = College.Status.REJECTED
        college.save(update_fields=["status", "updated_at"])
        logger.info("College rejected by %s: %s", request.user.username, college.name)
        messages.success(request, f"{college.name} has been rejected.")
    return redirect("dashboard:platform")


@role_required(User.Role.SUPER_ADMIN)
def suspend_college(request, pk):
    if request.method == "POST":
        college = get_object_or_404(College, pk=pk)
        college.status = College.Status.SUSPENDED
        college.save(update_fields=["status", "updated_at"])
        logger.info("College suspended by %s: %s", request.user.username, college.name)
        messages.warning(request, f"{college.name} has been suspended.")
    return redirect("dashboard:platform")


@role_required(User.Role.COLLEGE_ADMIN, User.Role.COLLEGE_STAFF)
def college_dashboard(request):
    """College Admin/Staff: stats and recent enquiries scoped strictly to
    their own college."""
    college = get_staff_college(request.user)
    if college is None:
        messages.error(request, "Your account is not linked to a college yet. Contact your Platform Admin.")
        return redirect("core:home")

    courses = Course.objects.filter(college=college)
    enquiries = Enquiry.objects.filter(college=college).select_related("course")[:10]
    stats = {
        "course_count": courses.count(),
        "active_course_count": courses.filter(is_active=True).count(),
        "enquiry_count": Enquiry.objects.filter(college=college).count(),
        "staff_count": college.staff_members.count(),
    }
    context = {"college": college, "courses": courses, "enquiries": enquiries, "stats": stats}
    return render(request, "dashboard/college_dashboard.html", context)


@role_required(User.Role.COLLEGE_ADMIN)
def manage_staff(request):
    """College Admin only: view and add College Staff for their own
    college. `college` is never taken from the form — always derived from
    the logged-in admin's own StaffProfile — this is what makes "college
    ownership" actually enforced rather than merely advisory.
    """
    college = get_staff_college(request.user)
    if college is None:
        messages.error(request, "Your account is not linked to a college yet. Contact your Platform Admin.")
        return redirect("core:home")

    if request.method == "POST":
        form = StaffCreationForm(request.POST)
        if form.is_valid():
            form.save(role=User.Role.COLLEGE_STAFF, college=college)
            messages.success(request, "Staff member added successfully.")
            return redirect("dashboard:manage_staff")
    else:
        form = StaffCreationForm()

    staff_members = college.staff_members.select_related("user").filter(user__role=User.Role.COLLEGE_STAFF)
    context = {"college": college, "staff_members": staff_members, "form": form}
    return render(request, "dashboard/manage_staff.html", context)


@role_required(User.Role.STUDENT)
def student_dashboard(request):
    """Student: profile summary. Enquiry tracking (linking a logged-in
    student's own submitted enquiries to their dashboard) is a future
    phase; the enquiry *submission* form itself now exists (Phase 4)."""
    return render(request, "dashboard/student_dashboard.html")


@role_required(User.Role.SUPER_ADMIN, User.Role.COLLEGE_ADMIN, User.Role.COLLEGE_STAFF)
def enquiry_list(request):
    """Phase 5 listing + Phase 6 search, filter & sort, paginated, always
    showing the associated College and Course for every row.

    College ownership: a Platform Admin sees every enquiry; a College
    Admin/Staff user only ever sees their own college's enquiries, scoped
    via get_staff_college(request.user) — never a college id taken from
    the URL or query string, matching the rest of this app. The same rule
    applies to the Phase 6 filters themselves: EnquiryFilterForm drops the
    "college" filter entirely for a College Admin/Staff user and restricts
    their "course" choices to their own college (see dashboard/forms.py).

    Search (`q`): case-insensitive substring match across student name,
    mobile, email, college name and course name (OR'd together).
    Filters: college (Platform Admin only), course, gender, status,
    admission year — all AND'd with search and each other.
    Sort: student / college / course / submission date, either direction
    (`sort` + `dir` query params); defaults to submission date, newest
    first, matching the model's default ordering.

    Every filter/sort/page link in the template is built by preserving the
    current querystring (see `querystring` in context), so paging through
    results or re-sorting never silently drops an active search or filter.
    """
    if request.user.role == User.Role.SUPER_ADMIN:
        college = None
        enquiries = Enquiry.objects.select_related("course", "college").all()
    else:
        college = get_staff_college(request.user)
        if college is None:
            messages.error(request, "Your account is not linked to a college yet. Contact your Platform Admin.")
            return redirect("core:home")
        enquiries = Enquiry.objects.select_related("course", "college").filter(college=college)

    filter_form = EnquiryFilterForm(request.GET, staff_college=college)
    filter_form.is_valid()  # triggers per-field cleaning; result intentionally unused, see form docstring
    cleaned = filter_form.cleaned_data

    search_term = cleaned.get("q")
    if search_term:
        enquiries = enquiries.filter(
            Q(full_name__icontains=search_term)
            | Q(mobile__icontains=search_term)
            | Q(email__icontains=search_term)
            | Q(college__name__icontains=search_term)
            | Q(course__course_name__icontains=search_term)
        )

    if college is None and cleaned.get("college"):
        enquiries = enquiries.filter(college=cleaned["college"])
    if cleaned.get("course"):
        enquiries = enquiries.filter(course=cleaned["course"])
    if cleaned.get("gender"):
        enquiries = enquiries.filter(gender=cleaned["gender"])
    if cleaned.get("status"):
        enquiries = enquiries.filter(status=cleaned["status"])
    if cleaned.get("admission_year"):
        enquiries = enquiries.filter(admission_year=cleaned["admission_year"])

    current_sort = cleaned.get("sort") or "submitted"
    current_dir = cleaned.get("dir") or "desc"
    order_field = SORT_FIELD_MAP.get(current_sort, "created_at")
    enquiries = enquiries.order_by(order_field if current_dir == "asc" else f"-{order_field}")

    paginator = Paginator(enquiries, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Querystring with 'page' stripped, reused by every pagination link so
    # changing pages never drops the active search/filter/sort.
    base_query = request.GET.copy()
    base_query.pop("page", None)
    querystring = base_query.urlencode()

    # A ready-to-use link (sort + toggled dir) for each sortable column
    # header. Clicking a column that's already active flips direction;
    # clicking a new column starts at ascending (submission date starts
    # descending — newest first — to match the default).
    sort_links = {}
    for key in SORT_FIELD_MAP:
        link_query = base_query.copy()
        if current_sort == key:
            link_query["dir"] = "desc" if current_dir == "asc" else "asc"
        else:
            link_query["dir"] = "desc" if key == "submitted" else "asc"
        link_query["sort"] = key
        sort_links[key] = f"?{link_query.urlencode()}"

    context = {
        "college": college,
        "page_obj": page_obj,
        "enquiries": page_obj.object_list,
        "total_count": paginator.count,
        "filter_form": filter_form,
        "querystring": querystring,
        "current_sort": current_sort,
        "current_dir": current_dir,
        "sort_links": sort_links,
        "is_filtered": bool(
            search_term
            or cleaned.get("college")
            or cleaned.get("course")
            or cleaned.get("gender")
            or cleaned.get("status")
            or cleaned.get("admission_year")
        ),
    }
    return render(request, "dashboard/enquiry_list.html", context)


@role_required(User.Role.SUPER_ADMIN, User.Role.COLLEGE_ADMIN, User.Role.COLLEGE_STAFF)
def enquiry_detail(request, pk):
    """Phase 5: full detail view for a single enquiry.

    A College Admin/Staff user gets a 404 (not a 403) for another
    college's enquiry, so a guessed URL can't even confirm that a given
    enquiry id exists at another college. A Platform Admin can view any
    (non-deleted) enquiry.
    """
    queryset = Enquiry.objects.select_related("course", "college", "submitted_by")
    if request.user.role == User.Role.SUPER_ADMIN:
        enquiry = get_object_or_404(queryset, pk=pk)
    else:
        college = get_staff_college(request.user)
        if college is None:
            messages.error(request, "Your account is not linked to a college yet. Contact your Platform Admin.")
            return redirect("core:home")
        enquiry = get_object_or_404(queryset, pk=pk, college=college)

    return render(request, "dashboard/enquiry_detail.html", {"enquiry": enquiry})
