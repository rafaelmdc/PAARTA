from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.browser.models import PipelineRun
from apps.imports.models import DeletionJob
from apps.imports.services.deletion.cache import bump_catalog_version
from apps.imports.services.deletion.safety import validate_deletion_target


def queue_deletion(
    pipeline_run: PipelineRun,
    *,
    reason: str = "",
    requested_by=None,
    requested_by_label: str = "",
) -> DeletionJob:
    """Mark pipeline_run as deleting, create or reuse a DeletionJob, and enqueue the Celery task.

    All synchronous work (lock, hide, bump cache, enqueue) happens in one
    transaction. The Celery task is dispatched via transaction.on_commit().

    Returns the DeletionJob (new or reused active job).
    """
    with transaction.atomic():
        locked_run = PipelineRun.objects.select_for_update().get(pk=pipeline_run.pk)

        validate_deletion_target(locked_run)

        existing_job = DeletionJob.objects.filter(
            pipeline_run=locked_run,
            status__in=[DeletionJob.Status.PENDING, DeletionJob.Status.RUNNING],
        ).first()
        if existing_job is not None:
            return existing_job

        label = requested_by_label or (str(requested_by) if requested_by else "")
        job = DeletionJob.objects.create(
            pipeline_run=locked_run,
            reason=reason,
            requested_by=requested_by,
            requested_by_label=label,
        )

        locked_run.lifecycle_status = PipelineRun.LifecycleStatus.DELETING
        locked_run.deleting_at = timezone.now()
        locked_run.deletion_reason = reason
        locked_run.save(update_fields=["lifecycle_status", "deleting_at", "deletion_reason"])

        new_version = bump_catalog_version()
        job.catalog_versions = [new_version]
        job.save(update_fields=["catalog_versions"])

        job_pk = job.pk
        transaction.on_commit(lambda: _enqueue(job_pk))

    return job


def _enqueue(job_pk: int) -> None:
    from apps.imports.tasks import delete_pipeline_run_job
    delete_pipeline_run_job.delay(job_pk)


def retry_deletion(job: DeletionJob) -> DeletionJob:
    """Re-enqueue a failed DeletionJob.

    Only FAILED jobs are eligible. The same job row is reused: retry_count is
    incremented, error fields are cleared, status is reset to PENDING, and the
    Celery task is dispatched via transaction.on_commit().
    """
    from apps.imports.services.deletion.safety import DeletionTargetError

    if job.status != DeletionJob.Status.FAILED:
        raise DeletionTargetError(
            f"DeletionJob {job.pk} has status={job.status!r}. Only failed jobs can be retried."
        )

    with transaction.atomic():
        locked_job = DeletionJob.objects.select_for_update().get(pk=job.pk)

        if locked_job.status != DeletionJob.Status.FAILED:
            raise DeletionTargetError(
                f"DeletionJob {locked_job.pk} is no longer failed (status={locked_job.status!r})."
            )

        locked_job.status = DeletionJob.Status.PENDING
        locked_job.phase = ""
        locked_job.error_message = ""
        locked_job.error_debug = {}
        locked_job.last_error_at = None
        locked_job.retry_count += 1
        locked_job.save(update_fields=[
            "status", "phase", "error_message", "error_debug",
            "last_error_at", "retry_count",
        ])

        job_pk = locked_job.pk
        transaction.on_commit(lambda: _enqueue(job_pk))

    return locked_job


def get_active_job(pipeline_run: PipelineRun) -> DeletionJob | None:
    """Return the pending or running DeletionJob for pipeline_run, or None."""
    return (
        DeletionJob.objects.filter(
            pipeline_run=pipeline_run,
            status__in=[DeletionJob.Status.PENDING, DeletionJob.Status.RUNNING],
        )
        .select_for_update(skip_locked=True)
        .first()
    )
