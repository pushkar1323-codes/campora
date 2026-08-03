"""
Views for the Notification Center. Every view is login_required only —
a Notification always belongs to exactly one recipient
(notifications.models.Notification.recipient), so ownership scoping is
simply "recipient=request.user" everywhere, the same way
admissions.views.enquiry_self_edit scopes by submitted_by=request.user.
There is no college-ownership dimension here: a notification's *subject*
may belong to a college, but the notification itself belongs to a person.
"""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .services import NotificationService


@login_required
def notification_list(request):
    """Full 'View All' page — every notification for the logged-in user,
    paginated, newest first. Read/unread state is shown per row (styled
    distinctly); opening this page does NOT bulk-mark everything read —
    that's the explicit "Mark all read" action below, kept as a deliberate
    user action rather than an automatic side effect of visiting the page,
    so a user can still tell what they haven't looked at yet even after
    opening the list.
    """
    notifications_qs = NotificationService.get_notifications(request.user)
    paginator = Paginator(notifications_qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "notifications/notification_list.html", {"page_obj": page_obj})


@login_required
def notification_mark_read(request, pk):
    """Click-through: marks one notification read, then sends the user to
    wherever it points (action_url), falling back to the full list if none
    was set. Matches an existing precedent in this codebase —
    dashboard.views.contact_message_detail already marks its subject read
    as a side effect of a plain GET, on the same "opening it counts as
    having reviewed it" reasoning — so this being reachable via a normal
    link click (not a POST-only form) is consistent, not a new pattern.
    """
    notification = get_object_or_404(NotificationService.get_notifications(request.user), pk=pk)
    NotificationService.mark_read(notification)
    return redirect(notification.action_url or "notifications:list")


@login_required
def notification_mark_all_read(request):
    if request.method == "POST":
        NotificationService.mark_all_read(request.user)
    return redirect(request.POST.get("next") or "notifications:list")


@login_required
def notification_unread_count(request):
    """Lightweight JSON endpoint the navbar bell polls to refresh its
    badge without a full page reload."""
    return JsonResponse({"unread_count": NotificationService.get_unread_count(request.user)})
