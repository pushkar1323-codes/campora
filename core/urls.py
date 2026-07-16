from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('colleges/', views.colleges, name='colleges'),
    path('colleges/<slug:slug>/', views.college_detail, name='college_detail'),
    path('courses/', views.courses, name='courses'),
    path('contact/', views.contact, name='contact'),
]
