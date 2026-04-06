"""URL configuration scaffold for the future HomoRepeat web app."""

from django.http import JsonResponse
from django.urls import path


def healthcheck(_request):
    return JsonResponse({"status": "ok", "app": "homorepeat-web"})


urlpatterns = [
    path("", healthcheck, name="healthcheck"),
]
