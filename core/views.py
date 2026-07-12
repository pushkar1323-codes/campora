from django.shortcuts import render


def home(request):
    """Public home page. Full hero/about/courses/CTA sections are built in Phase 3."""
    return render(request, 'core/home.html')


def about(request):
    return render(request, 'core/about.html')


def courses(request):
    return render(request, 'core/courses.html')


def contact(request):
    return render(request, 'core/contact.html')
