# school/urls.py

from django.urls import path
from .views import ProprietorDashboardView, ReceiptView

app_name = 'school'   # Namespace — lets you reference URLs as 'school:dashboard'

urlpatterns = [
    path(
        '',                             # Empty string = the homepage URL "/"
        ProprietorDashboardView.as_view(),
        name='dashboard'                # Nickname for this URL
    ),
    path('', ProprietorDashboardView.as_view(), name='dashboard'),
    path(
        'receipt/<str:receipt_number>/',
        ReceiptView.as_view(),
        name='receipt'
    ),
]