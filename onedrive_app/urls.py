from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='onedrive_login'),
    path('callback/', views.auth_callback, name='onedrive_callback'),
    path('upload/', views.upload_view, name='onedrive_upload'),
]
