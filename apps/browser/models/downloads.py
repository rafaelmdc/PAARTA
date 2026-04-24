from django.contrib.auth import get_user_model
from django.db import models


class DownloadBuild(models.Model):
    """Durable record for an async download artifact build.

    All current downloads are inline-streamed (sync) and never create a
    DownloadBuild row. This model is the data contract for Phase 6, when
    heavy exports that exceed acceptable request latency are promoted to
    async+persisted via a Celery task on the 'downloads' queue.

    Status lifecycle: PENDING → BUILDING → READY
                                        ↘ FAILED
                      READY → EXPIRED
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        BUILDING = "building", "Building"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    build_type = models.CharField(max_length=64, db_index=True)
    scope_key = models.CharField(max_length=128, db_index=True)
    catalog_version = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    requested_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    artifact_path = models.CharField(max_length=500, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    checksum = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["build_type", "scope_key", "catalog_version"],
                name="browser_dlbuild_lookup_idx",
            ),
        ]

    def __str__(self):
        return f"{self.build_type} [{self.status}] @ v{self.catalog_version}"

    @property
    def is_ready(self) -> bool:
        return self.status == self.Status.READY

    @property
    def is_terminal(self) -> bool:
        return self.status in (self.Status.READY, self.Status.FAILED, self.Status.EXPIRED)
