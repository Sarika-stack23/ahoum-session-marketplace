"""
Root URL configuration for Sessions Marketplace.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/sessions/", include("sessions_app.urls")),
    path("api/bookings/", include("bookings.urls")),
    path("api/", include("health.urls")),
]
