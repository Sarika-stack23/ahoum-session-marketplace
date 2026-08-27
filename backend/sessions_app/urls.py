from django.urls import path
from . import views

urlpatterns = [
    # Public
    path("", views.SessionListView.as_view(), name="session-list"),
    path("<int:pk>/", views.SessionDetailView.as_view(), name="session-detail"),
    # Creator-only
    path("create/", views.SessionCreateView.as_view(), name="session-create"),
    path("<int:pk>/update/", views.SessionUpdateView.as_view(), name="session-update"),
    path("<int:pk>/delete/", views.SessionDeleteView.as_view(), name="session-delete"),
    path("mine/", views.CreatorSessionListView.as_view(), name="creator-sessions"),
]
