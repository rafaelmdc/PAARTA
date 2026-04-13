from __future__ import annotations

from typing import Iterable

from django.utils import timezone

from apps.browser.models.operations import (
    AccessionCallCount,
    AccessionStatus,
    DownloadManifestEntry,
    NormalizationWarning,
)
from apps.browser.models.repeat_calls import RunParameter
from apps.browser.models.runs import AcquisitionBatch, PipelineRun
from apps.imports.models import ImportBatch
from apps.imports.services.published_run import (
    BatchArtifactPaths,
    ImportContractError,
    iter_download_manifest_rows,
    iter_normalization_warning_rows,
)

from .copy import BULK_CREATE_BATCH_SIZE, _copy_rows_to_model
from .state import ImportPhase, _ImportBatchStateReporter, _set_batch_state


def _create_run_parameters(
    pipeline_run: PipelineRun,
    rows: list[dict[str, object]],
) -> None:
    RunParameter.objects.bulk_create(
        [
            RunParameter(
                pipeline_run=pipeline_run,
                method=str(row["method"]),
                repeat_residue=str(row.get("repeat_residue", "")),
                param_name=str(row["param_name"]),
                param_value=str(row["param_value"]),
            )
            for row in rows
        ],
        batch_size=BULK_CREATE_BATCH_SIZE,
    )


def _create_download_manifest_entries(
    pipeline_run: PipelineRun,
    rows: list[dict[str, object]],
    batch_by_batch_id: dict[str, AcquisitionBatch],
) -> None:
    DownloadManifestEntry.objects.bulk_create(
        [
            DownloadManifestEntry(
                pipeline_run=pipeline_run,
                batch_id=_require_batch_pk(row.get("batch_id"), batch_by_batch_id, "download manifest"),
                assembly_accession=str(row["assembly_accession"]),
                download_status=str(row.get("download_status", "")),
                package_mode=str(row.get("package_mode", "")),
                download_path=str(row.get("download_path", "")),
                rehydrated_path=str(row.get("rehydrated_path", "")),
                checksum=str(row.get("checksum", "")),
                file_size_bytes=row.get("file_size_bytes"),
                download_started_at=row.get("download_started_at"),
                download_finished_at=row.get("download_finished_at"),
                notes=str(row.get("notes", "")),
            )
            for row in rows
        ],
        batch_size=BULK_CREATE_BATCH_SIZE,
    )


def _create_normalization_warning_rows(
    pipeline_run: PipelineRun,
    rows: list[dict[str, object]],
    batch_by_batch_id: dict[str, AcquisitionBatch],
) -> None:
    NormalizationWarning.objects.bulk_create(
        [
            NormalizationWarning(
                pipeline_run=pipeline_run,
                batch_id=_require_batch_pk(row.get("batch_id"), batch_by_batch_id, "normalization warning"),
                warning_code=str(row.get("warning_code", "")),
                warning_scope=str(row.get("warning_scope", "")),
                warning_message=str(row.get("warning_message", "")),
                genome_id=str(row.get("genome_id", "")),
                sequence_id=str(row.get("sequence_id", "")),
                protein_id=str(row.get("protein_id", "")),
                assembly_accession=str(row.get("assembly_accession", "")),
                source_file=str(row.get("source_file", "")),
                source_record_id=str(row.get("source_record_id", "")),
            )
            for row in rows
        ],
        batch_size=BULK_CREATE_BATCH_SIZE,
    )


def _create_accession_status_rows(
    pipeline_run: PipelineRun,
    rows: list[dict[str, object]],
    batch_by_batch_id: dict[str, AcquisitionBatch],
) -> None:
    AccessionStatus.objects.bulk_create(
        [
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
            for row in rows
        ],
        batch_size=BULK_CREATE_BATCH_SIZE,
    )


def _create_accession_call_count_rows(
    pipeline_run: PipelineRun,
    rows: list[dict[str, object]],
    batch_by_batch_id: dict[str, AcquisitionBatch],
) -> None:
    AccessionCallCount.objects.bulk_create(
        [
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
            for row in rows
        ],
        batch_size=BULK_CREATE_BATCH_SIZE,
    )


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


def _create_download_manifest_entries_streamed(
    batch: ImportBatch,
    pipeline_run: PipelineRun,
    batch_paths: Iterable[BatchArtifactPaths],
    batch_by_batch_id: dict[str, AcquisitionBatch],
    *,
    reporter: _ImportBatchStateReporter | None = None,
) -> int:
    count = 0
    buffer: list[DownloadManifestEntry] = []
    for batch_path in batch_paths:
        for row in iter_download_manifest_rows(batch_path.download_manifest_tsv, batch_id=batch_path.batch_id):
            buffer.append(
                DownloadManifestEntry(
                    pipeline_run=pipeline_run,
                    batch_id=_require_batch_pk(row.get("batch_id"), batch_by_batch_id, "download manifest"),
                    assembly_accession=str(row["assembly_accession"]),
                    download_status=str(row.get("download_status", "")),
                    package_mode=str(row.get("package_mode", "")),
                    download_path=str(row.get("download_path", "")),
                    rehydrated_path=str(row.get("rehydrated_path", "")),
                    checksum=str(row.get("checksum", "")),
                    file_size_bytes=row.get("file_size_bytes"),
                    download_started_at=row.get("download_started_at"),
                    download_finished_at=row.get("download_finished_at"),
                    notes=str(row.get("notes", "")),
                )
            )
            count += 1
            if len(buffer) >= BULK_CREATE_BATCH_SIZE:
                DownloadManifestEntry.objects.bulk_create(buffer, batch_size=BULK_CREATE_BATCH_SIZE)
                buffer = []
        _set_batch_state(
            batch,
            phase=ImportPhase.IMPORTING,
            progress_payload={
                "message": "Importing batch download manifest rows.",
                "batch_id": batch_path.batch_id,
                "download_manifest_entries": count,
            },
            reporter=reporter,
        )
    if buffer:
        DownloadManifestEntry.objects.bulk_create(buffer, batch_size=BULK_CREATE_BATCH_SIZE)
    return count


def _create_normalization_warning_rows_streamed(
    batch: ImportBatch,
    pipeline_run: PipelineRun,
    batch_paths: Iterable[BatchArtifactPaths],
    batch_by_batch_id: dict[str, AcquisitionBatch],
    *,
    reporter: _ImportBatchStateReporter | None = None,
) -> int:
    count = 0
    warning_timestamp = timezone.now()
    copy_count = _copy_rows_to_model(
        NormalizationWarning,
        [
            "created_at",
            "updated_at",
            "pipeline_run",
            "batch",
            "warning_code",
            "warning_scope",
            "warning_message",
            "genome_id",
            "sequence_id",
            "protein_id",
            "assembly_accession",
            "source_file",
            "source_record_id",
        ],
        (
            (
                warning_timestamp,
                warning_timestamp,
                pipeline_run.pk,
                _require_batch_pk(row.get("batch_id"), batch_by_batch_id, "normalization warning"),
                str(row.get("warning_code", "")),
                str(row.get("warning_scope", "")),
                str(row.get("warning_message", "")),
                str(row.get("genome_id", "")),
                str(row.get("sequence_id", "")),
                str(row.get("protein_id", "")),
                str(row.get("assembly_accession", "")),
                str(row.get("source_file", "")),
                str(row.get("source_record_id", "")),
            )
            for batch_path in batch_paths
            for row in iter_normalization_warning_rows(
                batch_path.normalization_warnings_tsv,
                batch_id=batch_path.batch_id,
            )
        ),
        batch=batch,
        reporter=reporter,
        progress_message="Bulk-loading normalization warning rows.",
        progress_key="normalization_warnings",
    )
    if copy_count is not None:
        return copy_count

    buffer: list[NormalizationWarning] = []
    for batch_path in batch_paths:
        for row in iter_normalization_warning_rows(
            batch_path.normalization_warnings_tsv,
            batch_id=batch_path.batch_id,
        ):
            buffer.append(
                NormalizationWarning(
                    pipeline_run=pipeline_run,
                    batch_id=_require_batch_pk(row.get("batch_id"), batch_by_batch_id, "normalization warning"),
                    warning_code=str(row.get("warning_code", "")),
                    warning_scope=str(row.get("warning_scope", "")),
                    warning_message=str(row.get("warning_message", "")),
                    genome_id=str(row.get("genome_id", "")),
                    sequence_id=str(row.get("sequence_id", "")),
                    protein_id=str(row.get("protein_id", "")),
                    assembly_accession=str(row.get("assembly_accession", "")),
                    source_file=str(row.get("source_file", "")),
                    source_record_id=str(row.get("source_record_id", "")),
                )
            )
            count += 1
            if len(buffer) >= BULK_CREATE_BATCH_SIZE:
                NormalizationWarning.objects.bulk_create(buffer, batch_size=BULK_CREATE_BATCH_SIZE)
                buffer = []
        _set_batch_state(
            batch,
            phase=ImportPhase.IMPORTING,
            progress_payload={
                "message": "Importing normalization warning rows.",
                "batch_id": batch_path.batch_id,
                "normalization_warnings": count,
            },
            reporter=reporter,
        )
    if buffer:
        NormalizationWarning.objects.bulk_create(buffer, batch_size=BULK_CREATE_BATCH_SIZE)
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
