from __future__ import annotations

from typing import Iterable

from apps.browser.models.operations import AccessionCallCount, AccessionStatus
from apps.browser.models.repeat_calls import RunParameter
from apps.browser.models.runs import AcquisitionBatch, PipelineRun
from apps.imports.services.published_run import ImportContractError

from .copy import BULK_CREATE_BATCH_SIZE


def _create_run_parameters_streamed(
    pipeline_run: PipelineRun,
    rows: Iterable[dict[str, object]],
) -> int:
    count = 0
    buffer: list[RunParameter] = []
    for row in rows:
        buffer.append(
            RunParameter(
                pipeline_run=pipeline_run,
                method=str(row["method"]),
                repeat_residue=str(row.get("repeat_residue", "")),
                param_name=str(row["param_name"]),
                param_value=str(row["param_value"]),
            )
        )
        count += 1
        if len(buffer) >= BULK_CREATE_BATCH_SIZE:
            RunParameter.objects.bulk_create(buffer, batch_size=BULK_CREATE_BATCH_SIZE)
            buffer = []
    if buffer:
        RunParameter.objects.bulk_create(buffer, batch_size=BULK_CREATE_BATCH_SIZE)
    return count


def _create_accession_status_rows_streamed(
    pipeline_run: PipelineRun,
    rows: Iterable[dict[str, object]],
    batch_by_batch_id: dict[str, AcquisitionBatch],
) -> int:
    count = 0
    buffer: list[AccessionStatus] = []
    for row in rows:
        buffer.append(
            AccessionStatus(
                pipeline_run=pipeline_run,
                batch_id=_require_batch_pk(row.get("batch_id"), batch_by_batch_id, "accession status"),
                assembly_accession=str(row["assembly_accession"]),
                download_status=str(row.get("download_status", "")),
                normalize_status=str(row.get("normalize_status", "")),
                translate_status=str(row.get("translate_status", "")),
                detect_status=str(row.get("detect_status", "")),
                finalize_status=str(row.get("finalize_status", "")),
                terminal_status=str(row.get("terminal_status", "")),
                failure_stage=str(row.get("failure_stage", "")),
                failure_reason=str(row.get("failure_reason", "")),
                n_genomes=int(row.get("n_genomes", 0)),
                n_proteins=int(row.get("n_proteins", 0)),
                n_repeat_calls=int(row.get("n_repeat_calls", 0)),
                notes=str(row.get("notes", "")),
            )
        )
        count += 1
        if len(buffer) >= BULK_CREATE_BATCH_SIZE:
            AccessionStatus.objects.bulk_create(buffer, batch_size=BULK_CREATE_BATCH_SIZE)
            buffer = []
    if buffer:
        AccessionStatus.objects.bulk_create(buffer, batch_size=BULK_CREATE_BATCH_SIZE)
    return count


def _create_accession_call_count_rows_streamed(
    pipeline_run: PipelineRun,
    rows: Iterable[dict[str, object]],
    batch_by_batch_id: dict[str, AcquisitionBatch],
) -> int:
    count = 0
    buffer: list[AccessionCallCount] = []
    for row in rows:
        buffer.append(
            AccessionCallCount(
                pipeline_run=pipeline_run,
                batch_id=_require_batch_pk(row.get("batch_id"), batch_by_batch_id, "accession call count"),
                assembly_accession=str(row["assembly_accession"]),
                method=str(row["method"]),
                repeat_residue=str(row.get("repeat_residue", "")),
                detect_status=str(row.get("detect_status", "")),
                finalize_status=str(row.get("finalize_status", "")),
                n_repeat_calls=int(row.get("n_repeat_calls", 0)),
            )
        )
        count += 1
        if len(buffer) >= BULK_CREATE_BATCH_SIZE:
            AccessionCallCount.objects.bulk_create(buffer, batch_size=BULK_CREATE_BATCH_SIZE)
            buffer = []
    if buffer:
        AccessionCallCount.objects.bulk_create(buffer, batch_size=BULK_CREATE_BATCH_SIZE)
    return count


def _require_batch_pk(
    batch_id: object,
    batch_by_batch_id: dict[str, AcquisitionBatch],
    label: str,
) -> int:
    batch_key = str(batch_id or "")
    batch = batch_by_batch_id.get(batch_key)
    if batch is None:
        raise ImportContractError(f"{label.capitalize()} row references missing batch_id {batch_id!r}")
    return batch.pk
