from django.http import JsonResponse
from django.views.generic import View

from apps.browser.models import PayloadBuild


class PayloadBuildStatusView(View):
    """JSON status endpoint for async stats bundle builds.

    Used by Phase 6+ frontend polling: GET /browser/payload-builds/<pk>/status/
    Returns build state and readiness so the client can decide whether to wait
    or render a placeholder while the payload_graph worker completes the build.
    """

    def get(self, request, pk):
        try:
            build = PayloadBuild.objects.get(pk=pk)
        except PayloadBuild.DoesNotExist:
            return JsonResponse({"error": "not found"}, status=404)

        return JsonResponse({
            "id": build.pk,
            "build_type": build.build_type,
            "status": build.status,
            "is_ready": build.is_ready,
            "catalog_version": build.catalog_version,
            "created_at": build.created_at.isoformat(),
            "started_at": build.started_at.isoformat() if build.started_at else None,
            "finished_at": build.finished_at.isoformat() if build.finished_at else None,
            "error_message": build.error_message or None,
        })
