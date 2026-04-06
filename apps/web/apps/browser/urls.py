from django.urls import path

from .views import BrowserHomeView


app_name = "browser"

urlpatterns = [
    path("", BrowserHomeView.as_view(), name="home"),
]
