from django.urls import path
from . import views

urlpatterns = [
    path("github/callback/", views.github_callback, name="github-callback"),
    path("token/refresh/", views.token_refresh, name="token-refresh"),
    path("profile/", views.profile, name="profile"),
    path("logout/", views.logout, name="logout"),
]
