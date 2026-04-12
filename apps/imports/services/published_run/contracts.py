from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


GENOME_REQUIRED_COLUMNS = [
    "genome_id",
    "source",
    "accession",
    "genome_name",
    "assembly_type",
    "taxon_id",
]
TAXONOMY_REQUIRED_COLUMNS = [
    "taxon_id",
    "taxon_name",
    "parent_taxon_id",
    "rank",
    "source",
]
SEQUENCE_REQUIRED_COLUMNS = [
    "sequence_id",
    "genome_id",
    "sequence_name",
    "sequence_length",
]
PROTEIN_REQUIRED_COLUMNS = [
    "protein_id",
    "sequence_id",
    "genome_id",
    "protein_name",
    "protein_length",
]
DOWNLOAD_MANIFEST_REQUIRED_COLUMNS = [
    "batch_id",
    "assembly_accession",
    "download_status",
    "package_mode",
    "download_path",
    "rehydrated_path",
    "checksum",
    "file_size_bytes",
    "download_started_at",
    "download_finished_at",
    "notes",
]
NORMALIZATION_WARNING_REQUIRED_COLUMNS = [
    "warning_code",
    "warning_scope",
    "warning_message",
    "batch_id",
    "genome_id",
    "sequence_id",
    "protein_id",
    "assembly_accession",
    "source_file",
    "source_record_id",
]
ACCESSION_STATUS_REQUIRED_COLUMNS = [
    "assembly_accession",
    "batch_id",
    "download_status",
    "normalize_status",
    "translate_status",
    "detect_status",
    "finalize_status",
    "terminal_status",
    "failure_stage",
    "failure_reason",
    "n_genomes",
    "n_proteins",
    "n_repeat_calls",
    "notes",
]
ACCESSION_CALL_COUNT_REQUIRED_COLUMNS = [
    "assembly_accession",
    "batch_id",
    "method",
    "repeat_residue",
    "detect_status",
    "finalize_status",
    "n_repeat_calls",
]
RUN_PARAM_REQUIRED_COLUMNS = ["method", "repeat_residue", "param_name", "param_value"]
REPEAT_CALL_REQUIRED_COLUMNS = [
    "call_id",
    "method",
    "genome_id",
    "taxon_id",
    "sequence_id",
    "protein_id",
    "start",
    "end",
    "length",
    "repeat_residue",
    "repeat_count",
    "non_repeat_count",
    "purity",
    "aa_sequence",
]
MANIFEST_REQUIRED_KEYS = [
    "run_id",
    "status",
    "started_at_utc",
    "finished_at_utc",
    "profile",
    "acquisition_publish_mode",
    "git_revision",
    "inputs",
    "paths",
    "params",
    "enabled_methods",
    "repeat_residues",
    "artifacts",
]
ACQUISITION_VALIDATION_REQUIRED_KEYS = [
    "status",
    "scope",
    "counts",
    "checks",
    "failed_accessions",
    "warning_summary",
    "notes",
]
ACQUISITION_VALIDATION_COUNT_KEYS = [
    "n_selected_assemblies",
    "n_downloaded_packages",
    "n_genomes",
    "n_sequences",
    "n_proteins",
    "n_warning_rows",
]
VALID_METHODS = {"pure", "threshold", "seed_extend"}


class ImportContractError(ValueError):
    """Raised when a published run does not satisfy the import contract."""


@dataclass(frozen=True)
class BatchArtifactPaths:
    batch_id: str
    batch_root: Path
    genomes_tsv: Path
    taxonomy_tsv: Path
    sequences_tsv: Path
    proteins_tsv: Path
    cds_fna: Path
    proteins_faa: Path
    download_manifest_tsv: Path
    normalization_warnings_tsv: Path
    acquisition_validation_json: Path


@dataclass(frozen=True)
class RepeatLinkedIds:
    genome_ids: tuple[str, ...]
    sequence_ids: tuple[str, ...]
    protein_ids: tuple[str, ...]


@dataclass(frozen=True)
class ParsedAcquisitionBatch:
    artifact_paths: BatchArtifactPaths
    acquisition_validation: dict[str, Any]
    total_genomes: int
    total_sequences: int
    total_proteins: int
    total_download_manifest_rows: int
    total_normalization_warning_rows: int
    total_repeat_calls: int
    total_repeat_linked_genomes: int
    total_repeat_linked_sequences: int
    total_repeat_linked_proteins: int


@dataclass(frozen=True)
class RequiredArtifactPaths:
    publish_root: Path
    manifest: Path
    acquisition_batches_root: Path
    acquisition_batches: tuple[BatchArtifactPaths, ...]
    accession_status_tsv: Path
    accession_call_counts_tsv: Path
    run_params_tsv: Path
    repeat_calls_tsv: Path


@dataclass(frozen=True)
class InspectedPublishedRun:
    artifact_paths: RequiredArtifactPaths
    manifest: dict[str, Any]
    pipeline_run: dict[str, Any]


@dataclass(frozen=True)
class ParsedPublishedRun:
    artifact_paths: RequiredArtifactPaths
    manifest: dict[str, Any]
    pipeline_run: dict[str, Any]
    batch_summaries: tuple[ParsedAcquisitionBatch, ...]
    taxonomy_rows: list[dict[str, Any]]
    genome_rows: list[dict[str, Any]]
    sequence_rows: list[dict[str, Any]]
    protein_rows: list[dict[str, Any]]
    download_manifest_rows: list[dict[str, Any]]
    normalization_warning_rows: list[dict[str, Any]]
    accession_status_rows: list[dict[str, Any]]
    accession_call_count_rows: list[dict[str, Any]]
    run_parameter_rows: list[dict[str, Any]]
    repeat_call_rows: list[dict[str, Any]]
    repeat_linked_ids: RepeatLinkedIds
