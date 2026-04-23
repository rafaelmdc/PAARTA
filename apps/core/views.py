import os

import httpx
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse
from django.views.generic import TemplateView

_FLOWER_INTERNAL_URL = os.getenv("FLOWER_INTERNAL_URL", "http://flower:5555")


class HomeView(TemplateView):
    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sections"] = [
            {
                "title": "Browser",
                "description": "Run-first browsing for taxa, genomes, proteins, and repeat calls.",
                "url_name": "browser:home",
            },
            {
                "title": "Imports",
                "description": "Staff-facing run import tooling built around published TSV contracts.",
                "url_name": "imports:home",
            },
        ]
        return context


def healthcheck(_request):
    return JsonResponse({"status": "ok", "app": "homorepeat-web"})


@staff_member_required
def flower_proxy(request, path=""):
    url = f"{_FLOWER_INTERNAL_URL}/admin/flower/{path}"
    if request.META.get("QUERY_STRING"):
        url += f"?{request.META['QUERY_STRING']}"
    try:
        resp = httpx.request(
            method=request.method,
            url=url,
            content=request.body,
            headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
            follow_redirects=False,
            timeout=30.0,
        )
    except httpx.ConnectError:
        return HttpResponse("Flower is not running.", status=503, content_type="text/plain")
    return HttpResponse(
        resp.content,
        status=resp.status_code,
        content_type=resp.headers.get("content-type", "text/html"),
    )
