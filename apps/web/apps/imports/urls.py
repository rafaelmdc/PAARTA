from django.urls import path

from .views import ImportsHomeView


app_name = "imports"

urlpatterns = [
    path("", ImportsHomeView.as_view(), name="home"),
]
