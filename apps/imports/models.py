import uuid
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.db.models import F, Q


CATALOG_VERSION_CACHE_KEY = "browser:stats:catalog_version"
CATALOG_VERSION_CACHE_TTL_SECONDS = 10


class CatalogVersion(models.Model):
    version = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(pk=1),
                name="imports_catalog_version_singleton",
            )
        ]

    @classmethod
    def current(cls) -> int:
        obj, _created = cls.objects.get_or_create(pk=1, defaults={"version": 0})
        return int(obj.version)

    @classmethod
    def cached_current(cls) -> int:
        cached = cache.get(CATALOG_VERSION_CACHE_KEY)
        if cached is not None:
            return int(cached)
        version = cls.current()
        cache.set(CATALOG_VERSION_CACHE_KEY, version, timeout=CATALOG_VERSION_CACHE_TTL_SECONDS)
        return version

    @classmethod
    def increment(cls) -> int:
        cls.objects.get_or_create(pk=1, defaults={"version": 0})
        cls.objects.filter(pk=1).update(version=F("version") + 1)
        cache.delete(CATALOG_VERSION_CACHE_KEY)
        return cls.current()


class ImportBatch(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    PROGRESS_STEPS = (
        ("queued", "Queued"),
        ("parsing_contract", "Check"),
        ("preparing_import", "Prepare"),
        ("staging_tables", "Stage"),
        ("importing_rows", "Rows"),
        ("syncing_canonical_catalog", "Catalog"),
        ("completed", "Done"),
    )

    pipeline_run = models.ForeignKey(
        "browser.PipelineRun",
        on_delete=models.SET_NULL,
        related_name="import_batches",
        blank=True,
        null=True,
    )
    source_path = models.CharField(max_length=500)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    replace_existing = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    celery_task_id = models.CharField(max_length=64, blank=True)
    success_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    phase = models.CharField(max_length=64, blank=True, db_index=True)
    heartbeat_at = models.DateTimeField(blank=True, null=True, db_index=True)
    progress_payload = models.JSONField(default=dict, blank=True)
    row_counts = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        if self.pipeline_run_id:
            return f"{self.pipeline_run.run_id} ({self.status})"
        return f"{self.source_path} ({self.status})"

    @property
    def progress_steps(self):
        phase_indexes = {phase: index for index, (phase, _label) in enumerate(self.PROGRESS_STEPS)}
        if self.status == self.Status.COMPLETED:
            current_index = phase_indexes["completed"]
        elif self.status == self.Status.FAILED:
            failed_phase = ""
            if isinstance(self.progress_payload, dict):
                failed_phase = str(self.progress_payload.get("failed_phase") or "")
            current_index = phase_indexes.get(failed_phase, phase_indexes.get(self.phase, len(self.PROGRESS_STEPS) - 1))
        else:
            current_index = phase_indexes.get(self.phase, 0)

        steps = []
        for index, (phase, label) in enumerate(self.PROGRESS_STEPS):
            state = "pending"
            if self.status == self.Status.COMPLETED:
                state = "complete"
            elif self.status == self.Status.FAILED:
                if index < current_index:
                    state = "complete"
                elif index == current_index:
                    state = "failed"
                    if phase == "completed":
                        label = "Failed"
            else:
                if index < current_index:
                    state = "complete"
                elif index == current_index:
                    state = "active"
            steps.append({"phase": phase, "label": label, "state": state})
        return steps


class UploadedRun(models.Model):
    class Status(models.TextChoices):
        RECEIVING = "receiving", "Receiving"
        RECEIVED = "received", "Received"
        EXTRACTING = "extracting", "Extracting"
        READY = "ready", "Ready"
        QUEUED = "queued", "Queued"
        IMPORTED = "imported", "Imported"
        FAILED = "failed", "Failed"

    original_filename = models.CharField(max_length=255)
    upload_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.RECEIVING,
        db_index=True,
    )
    size_bytes = models.BigIntegerField(default=0)
    received_bytes = models.BigIntegerField(default=0)
    chunk_size_bytes = models.PositiveIntegerField(default=8 * 1024 * 1024)
    total_chunks = models.PositiveIntegerField(default=0)
    received_chunks = models.JSONField(default=list, blank=True)
    publish_root = models.CharField(max_length=500, blank=True)
    run_id = models.CharField(max_length=200, blank=True, db_index=True)
    error_message = models.TextField(blank=True)
    file_sha256 = models.CharField(max_length=64, blank=True, null=True)
    assembled_sha256 = models.CharField(max_length=64, blank=True, null=True)
    checksum_status = models.CharField(max_length=32, blank=True, null=True)
    checksum_error = models.TextField(blank=True, null=True)
    import_batch = models.ForeignKey(
        "imports.ImportBatch",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="uploaded_runs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        label = self.run_id or self.original_filename
        return f"{label} ({self.status})"

    @property
    def upload_root(self) -> Path:
        return Path(settings.HOMOREPEAT_IMPORTS_ROOT) / "uploads" / str(self.upload_id)

    @property
    def chunks_root(self) -> Path:
        return self.upload_root / "chunks"

    @property
    def zip_path(self) -> Path:
        return self.upload_root / "source.zip"

    @property
    def extracted_root(self) -> Path:
        return self.upload_root / "extracted"

    @property
    def library_root(self) -> Path | None:
        if not self.run_id:
            return None
        return Path(settings.HOMOREPEAT_IMPORTS_ROOT) / "library" / self.run_id


class UploadedRunChunk(models.Model):
    """One row per accepted chunk — the fast-path manifest for status queries.

    The filesystem .part files remain the authoritative byte store; this table
    records the hash and metadata so Phase 2 status reconciliation can skip
    already-verified chunks without scanning the filesystem.
    """

    uploaded_run = models.ForeignKey(
        "imports.UploadedRun",
        on_delete=models.CASCADE,
        related_name="chunk_records",
    )
    chunk_index = models.PositiveIntegerField()
    size_bytes = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("uploaded_run", "chunk_index")]
