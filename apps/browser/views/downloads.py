from django.http import JsonResponse
from django.views.generic import View

from apps.browser.models import DownloadBuild


class DownloadBuildStatusView(View):
    """JSON status endpoint for async download artifact builds.

    Used by Phase 6 frontend polling: GET /browser/downloads/<pk>/status/
    Returns build state, readiness flag, and artifact metadata when ready.
    """

    def get(self, request, pk):
        try:
            build = DownloadBuild.objects.get(pk=pk)
        except DownloadBuild.DoesNotExist:
            return JsonResponse({"error": "not found"}, status=404)

        return JsonResponse({
            "id": build.pk,
            "build_type": build.build_type,
            "status": build.status,
            "is_ready": build.is_ready,
            "catalog_version": build.catalog_version,
            "created_at": build.created_at.isoformat(),
            "finished_at": build.finished_at.isoformat() if build.finished_at else None,
            "artifact_path": build.artifact_path or None,
            "size_bytes": build.size_bytes,
            "error_message": build.error_message or None,
        })
