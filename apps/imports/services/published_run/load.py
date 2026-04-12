from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from .artifacts import _resolve_batch_artifacts, resolve_required_artifacts
from .contracts import (
    BatchArtifactPaths,
    InspectedPublishedRun,
    ParsedAcquisitionBatch,
    ParsedPublishedRun,
    RepeatLinkedIds,
)
from .iterators import (
    iter_accession_call_count_rows,
    iter_accession_status_rows,
    iter_download_manifest_rows,
    iter_genome_rows,
    iter_normalization_warning_rows,
    iter_protein_rows,
    iter_repeat_call_rows,
    iter_run_parameter_rows,
    iter_sequence_rows,
    iter_taxonomy_rows,
)
from .manifest import (
    _ensure_raw_publish_mode,
    _normalize_pipeline_run,
    _read_acquisition_validation_payload,
    _read_manifest,
)


def inspect_published_run(publish_root: Path | str) -> InspectedPublishedRun:
    artifact_paths = resolve_required_artifacts(publish_root)
    manifest = _read_manifest(artifact_paths.manifest)
    _ensure_raw_publish_mode(manifest)
    batch_artifact_paths = _resolve_batch_artifacts(artifact_paths)
    artifact_paths = replace(artifact_paths, acquisition_batches=batch_artifact_paths)
    return InspectedPublishedRun(
        artifact_paths=artifact_paths,
        manifest=manifest,
        pipeline_run=_normalize_pipeline_run(manifest, artifact_paths),
    )


def load_published_run(publish_root: Path | str) -> ParsedPublishedRun:
    inspected = inspect_published_run(publish_root)
    artifact_paths = inspected.artifact_paths
    manifest = inspected.manifest
    batch_artifact_paths = artifact_paths.acquisition_batches

    raw_taxonomy_rows: list[dict[str, Any]] = []
    raw_genome_rows: list[dict[str, Any]] = []
    raw_sequence_rows: list[dict[str, Any]] = []
    raw_protein_rows: list[dict[str, Any]] = []
    download_manifest_rows: list[dict[str, Any]] = []
    normalization_warning_rows: list[dict[str, Any]] = []
    acquisition_validation_by_batch: dict[str, dict[str, Any]] = {}
    for batch_paths in batch_artifact_paths:
        raw_taxonomy_rows.extend(iter_taxonomy_rows(batch_paths.taxonomy_tsv))
        raw_genome_rows.extend(iter_genome_rows(batch_paths.genomes_tsv, batch_id=batch_paths.batch_id))
        raw_sequence_rows.extend(iter_sequence_rows(batch_paths.sequences_tsv, batch_id=batch_paths.batch_id))
        raw_protein_rows.extend(iter_protein_rows(batch_paths.proteins_tsv, batch_id=batch_paths.batch_id))
        download_manifest_rows.extend(
            iter_download_manifest_rows(batch_paths.download_manifest_tsv, batch_id=batch_paths.batch_id)
        )
        normalization_warning_rows.extend(
            iter_normalization_warning_rows(
                batch_paths.normalization_warnings_tsv,
                batch_id=batch_paths.batch_id,
            )
        )
        acquisition_validation_by_batch[batch_paths.batch_id] = _read_acquisition_validation_payload(
            batch_paths.acquisition_validation_json,
            batch_id=batch_paths.batch_id,
        )

    accession_status_rows = list(iter_accession_status_rows(artifact_paths.accession_status_tsv))
    accession_call_count_rows = list(iter_accession_call_count_rows(artifact_paths.accession_call_counts_tsv))
    run_parameter_rows = list(iter_run_parameter_rows(artifact_paths.run_params_tsv))
    repeat_call_rows = list(iter_repeat_call_rows(artifact_paths.repeat_calls_tsv))
    repeat_linked_ids = _build_repeat_linked_ids(repeat_call_rows)

    genome_rows = _merge_unique_rows(raw_genome_rows, key_field="genome_id", label="genome")
    sequence_rows = _merge_unique_rows(raw_sequence_rows, key_field="sequence_id", label="sequence")
    protein_rows = _merge_unique_rows(raw_protein_rows, key_field="protein_id", label="protein")

    return ParsedPublishedRun(
        artifact_paths=artifact_paths,
        manifest=manifest,
        pipeline_run=_normalize_pipeline_run(manifest, artifact_paths),
        batch_summaries=_build_batch_summaries(
            batch_artifact_paths=batch_artifact_paths,
            raw_genome_rows=raw_genome_rows,
            raw_sequence_rows=raw_sequence_rows,
            raw_protein_rows=raw_protein_rows,
            genome_rows=genome_rows,
            sequence_rows=sequence_rows,
            protein_rows=protein_rows,
            download_manifest_rows=download_manifest_rows,
            normalization_warning_rows=normalization_warning_rows,
            acquisition_validation_by_batch=acquisition_validation_by_batch,
            repeat_call_rows=repeat_call_rows,
            repeat_linked_ids=repeat_linked_ids,
        ),
        taxonomy_rows=_merge_unique_rows(raw_taxonomy_rows, key_field="taxon_id", label="taxonomy"),
        genome_rows=genome_rows,
        sequence_rows=sequence_rows,
        protein_rows=protein_rows,
        download_manifest_rows=download_manifest_rows,
        normalization_warning_rows=normalization_warning_rows,
        accession_status_rows=_merge_unique_rows(
            accession_status_rows,
            key_field="assembly_accession",
            label="accession status",
        ),
        accession_call_count_rows=_merge_unique_rows(
            accession_call_count_rows,
            key_field="unique_key",
            label="accession call count",
        ),
        run_parameter_rows=run_parameter_rows,
        repeat_call_rows=repeat_call_rows,
        repeat_linked_ids=repeat_linked_ids,
    )


def _build_repeat_linked_ids(repeat_call_rows: list[dict[str, Any]]) -> RepeatLinkedIds:
    return RepeatLinkedIds(
        genome_ids=tuple(sorted({str(row["genome_id"]) for row in repeat_call_rows})),
        sequence_ids=tuple(sorted({str(row["sequence_id"]) for row in repeat_call_rows})),
        protein_ids=tuple(sorted({str(row["protein_id"]) for row in repeat_call_rows})),
    )


def _build_batch_summaries(
    *,
    batch_artifact_paths: tuple[BatchArtifactPaths, ...],
    raw_genome_rows: list[dict[str, Any]],
    raw_sequence_rows: list[dict[str, Any]],
    raw_protein_rows: list[dict[str, Any]],
    genome_rows: list[dict[str, Any]],
    sequence_rows: list[dict[str, Any]],
    protein_rows: list[dict[str, Any]],
    download_manifest_rows: list[dict[str, Any]],
    normalization_warning_rows: list[dict[str, Any]],
    acquisition_validation_by_batch: dict[str, dict[str, Any]],
    repeat_call_rows: list[dict[str, Any]],
    repeat_linked_ids: RepeatLinkedIds,
) -> tuple[ParsedAcquisitionBatch, ...]:
    genome_batch_by_id = {str(row["genome_id"]): str(row["batch_id"]) for row in genome_rows}
    sequence_batch_by_id = {str(row["sequence_id"]): str(row["batch_id"]) for row in sequence_rows}
    protein_batch_by_id = {str(row["protein_id"]): str(row["batch_id"]) for row in protein_rows}

    summaries: list[ParsedAcquisitionBatch] = []
    for batch_paths in batch_artifact_paths:
        batch_id = batch_paths.batch_id
        summaries.append(
            ParsedAcquisitionBatch(
                artifact_paths=batch_paths,
                acquisition_validation=acquisition_validation_by_batch[batch_id],
                total_genomes=sum(1 for row in raw_genome_rows if str(row["batch_id"]) == batch_id),
                total_sequences=sum(1 for row in raw_sequence_rows if str(row["batch_id"]) == batch_id),
                total_proteins=sum(1 for row in raw_protein_rows if str(row["batch_id"]) == batch_id),
                total_download_manifest_rows=sum(
                    1 for row in download_manifest_rows if str(row["batch_id"]) == batch_id
                ),
                total_normalization_warning_rows=sum(
                    1 for row in normalization_warning_rows if str(row["batch_id"]) == batch_id
                ),
                total_repeat_calls=sum(
                    1 for row in repeat_call_rows if genome_batch_by_id.get(str(row["genome_id"])) == batch_id
                ),
                total_repeat_linked_genomes=sum(
                    1 for genome_id in repeat_linked_ids.genome_ids if genome_batch_by_id.get(genome_id) == batch_id
                ),
                total_repeat_linked_sequences=sum(
                    1
                    for sequence_id in repeat_linked_ids.sequence_ids
                    if sequence_batch_by_id.get(sequence_id) == batch_id
                ),
                total_repeat_linked_proteins=sum(
                    1
                    for protein_id in repeat_linked_ids.protein_ids
                    if protein_batch_by_id.get(protein_id) == batch_id
                ),
            )
        )
    return tuple(summaries)


def _merge_unique_rows(
    rows: list[dict[str, Any]],
    *,
    key_field: str,
    label: str,
) -> list[dict[str, Any]]:
    merged_by_key: dict[Any, dict[str, Any]] = {}
    ordered_keys: list[Any] = []

    for row in rows:
        key = row[key_field]
        existing = merged_by_key.get(key)
        if existing is None:
            merged_by_key[key] = row
            ordered_keys.append(key)
            continue
        if existing != row:
            raise ImportContractError(
                f"Conflicting duplicate {label} rows were found for {key_field}={key!r}"
            )

    return [merged_by_key[key] for key in ordered_keys]
