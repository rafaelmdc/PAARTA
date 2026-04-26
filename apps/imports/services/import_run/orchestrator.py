from __future__ import annotations

from django.utils import timezone

from apps.browser.models.runs import PipelineRun
from apps.imports.services.published_run import (
    ImportContractError,
)

from .entities import _delete_run_scoped_rows


def _upsert_pipeline_run(run_payload: dict[str, object], *, replace_existing: bool) -> PipelineRun:
    existing_run = PipelineRun.objects.filter(run_id=run_payload["run_id"]).first()
    if existing_run and not replace_existing:
        raise ImportContractError(
            f"Run {run_payload['run_id']!r} already exists. Re-run with --replace-existing to replace it."
        )

    if existing_run:
        _delete_run_scoped_rows(existing_run)
        pipeline_run = existing_run
        for field_name, value in run_payload.items():
            setattr(pipeline_run, field_name, value)
        pipeline_run.imported_at = timezone.now()
        pipeline_run.save()
        return pipeline_run

    return PipelineRun.objects.create(**run_payload)
