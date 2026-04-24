"""URL configuration for the HomoRepeat web project."""

from django.contrib import admin
from django.urls import include, path

from apps.core.views import flower_proxy

urlpatterns = [
    path("", include("apps.core.urls")),
    # Flower proxy must come before admin/ so it is matched before the catch-all.
    path("admin/flower/", flower_proxy),
    path("admin/flower/<path:path>", flower_proxy),
    path("admin/", admin.site.urls),
    path("browser/", include("apps.browser.urls")),
    path("imports/", include("apps.imports.urls")),
]
