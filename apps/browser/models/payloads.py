from django.db import models


class PayloadBuild(models.Model):
    """Durable record for an async stats bundle build on the payload_graph queue.

    Created either by the post-import warmup fan-out (pre-warming the default
    scope into cache after a successful import) or when a payload type is
    promoted to async+persisted in the stats payload policy.

    When the Celery task succeeds the payload is stored in the shared Redis
    cache under the bundle builder's normal key, so subsequent web requests
    pick it up via the usual build_or_get_cached path without any view change.

    Invalidation: scope_key is a hash of filter params (excluding catalog
    version). A new catalog_version produces a new scope_key and therefore a
    new PayloadBuild row. Old rows become unreachable and expire via Redis TTL.

    Status lifecycle: PENDING → BUILDING → READY
                                        ↘ FAILED
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        BUILDING = "building", "Building"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    build_type = models.CharField(max_length=64, db_index=True)
    scope_key = models.CharField(max_length=64, db_index=True)
    scope_params = models.JSONField(default=dict)
    catalog_version = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    celery_task_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["build_type", "scope_key", "catalog_version"],
                name="browser_pldbuild_lookup_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["build_type", "scope_key", "catalog_version"],
                name="browser_pldbuild_unique",
            ),
        ]

    def __str__(self):
        return f"{self.build_type} [{self.status}] @ v{self.catalog_version}"

    @property
    def is_ready(self) -> bool:
        return self.status == self.Status.READY

    @property
    def is_terminal(self) -> bool:
        return self.status in (self.Status.READY, self.Status.FAILED)
