# school/urls.py

from django.urls import path
from .views import ProprietorDashboardView

app_name = 'school'   # Namespace — lets you reference URLs as 'school:dashboard'

urlpatterns = [
    path(
        '',                             # Empty string = the homepage URL "/"
        ProprietorDashboardView.as_view(),
        name='dashboard'                # Nickname for this URL
    ),
]