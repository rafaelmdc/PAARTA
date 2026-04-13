from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from apps.imports.models import ImportBatch
from apps.imports.services.published_run import (
    ImportContractError,
    InspectedPublishedRun,
    ParsedPublishedRun,
    iter_repeat_call_rows,
)

from .copy import BULK_CREATE_BATCH_SIZE
from .state import ImportPhase, _ImportBatchStateReporter, _set_batch_state


@dataclass(frozen=True)
class PreparedImportData:
    retained_sequence_rows: list[dict[str, object]]
    retained_protein_rows: list[dict[str, object]]
    nucleotide_sequences_by_id: dict[str, str]
    amino_acid_sequences_by_id: dict[str, str]
    analyzed_protein_counts: dict[str, int]
    repeat_call_counts_by_protein: dict[str, int]


@dataclass(frozen=True)
class PreparedStreamedImportData:
    retained_genome_ids: frozenset[str]
    retained_sequence_ids: frozenset[str]
    retained_protein_ids: frozenset[str]
    repeat_call_counts_by_protein: dict[str, int]
    total_repeat_calls: int


def _prepare_streamed_import_data(
    batch: ImportBatch,
    inspected: InspectedPublishedRun,
    *,
    reporter: _ImportBatchStateReporter | None = None,
) -> PreparedStreamedImportData:
    retained_genome_ids: set[str] = set()
    retained_sequence_ids: set[str] = set()
    retained_protein_ids: set[str] = set()
    repeat_call_counts_by_protein: dict[str, int] = {}
    total_repeat_calls = 0

    for row in iter_repeat_call_rows(inspected.artifact_paths.repeat_calls_tsv):
        genome_id = str(row["genome_id"])
        sequence_id = str(row["sequence_id"])
        protein_id = str(row["protein_id"])
        retained_genome_ids.add(genome_id)
        retained_sequence_ids.add(sequence_id)
        retained_protein_ids.add(protein_id)
        repeat_call_counts_by_protein[protein_id] = repeat_call_counts_by_protein.get(protein_id, 0) + 1
        total_repeat_calls += 1
        if total_repeat_calls % BULK_CREATE_BATCH_SIZE == 0:
            _set_batch_state(
                batch,
                phase=ImportPhase.PREPARING,
                progress_payload={
                    "message": "Scanning repeat calls to determine retained sequence and protein IDs.",
                    "batch_count": len(inspected.artifact_paths.acquisition_batches),
                    "repeat_calls": total_repeat_calls,
                    "retained_sequences": len(retained_sequence_ids),
                    "retained_proteins": len(retained_protein_ids),
                },
                reporter=reporter,
            )

    return PreparedStreamedImportData(
        retained_genome_ids=frozenset(retained_genome_ids),
        retained_sequence_ids=frozenset(retained_sequence_ids),
        retained_protein_ids=frozenset(retained_protein_ids),
        repeat_call_counts_by_protein=repeat_call_counts_by_protein,
        total_repeat_calls=total_repeat_calls,
    )


def _select_repeat_linked_rows(
    genome_rows: list[dict[str, object]],
    sequence_rows: list[dict[str, object]],
    protein_rows: list[dict[str, object]],
    repeat_call_rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    genome_ids = {str(row["genome_id"]) for row in genome_rows}
    sequence_rows_by_id = {str(row["sequence_id"]): row for row in sequence_rows}
    protein_rows_by_id = {str(row["protein_id"]): row for row in protein_rows}

    for row in sequence_rows:
        genome_id = str(row["genome_id"])
        if genome_id not in genome_ids:
            raise ImportContractError(f"Sequence row references missing genome_id {row['genome_id']!r}")

    for row in protein_rows:
        genome_id = str(row["genome_id"])
        sequence_id = str(row["sequence_id"])
        if genome_id not in genome_ids:
            raise ImportContractError(f"Protein row references missing genome_id {row['genome_id']!r}")
        if sequence_id not in sequence_rows_by_id:
            raise ImportContractError(f"Protein row references missing sequence_id {row['sequence_id']!r}")

    retained_sequence_ids: set[str] = set()
    retained_protein_ids: set[str] = set()

    for row in repeat_call_rows:
        genome_id = str(row["genome_id"])
        sequence_id = str(row["sequence_id"])
        protein_id = str(row["protein_id"])

        if genome_id not in genome_ids:
            raise ImportContractError(
                f"Repeat call row references missing genome_id {row['genome_id']!r}"
            )

        sequence_row = sequence_rows_by_id.get(sequence_id)
        if sequence_row is None:
            raise ImportContractError(
                f"Repeat call row references missing sequence_id {row['sequence_id']!r}"
            )

        protein_row = protein_rows_by_id.get(protein_id)
        if protein_row is None:
            raise ImportContractError(
                f"Repeat call row references missing protein_id {row['protein_id']!r}"
            )

        if str(sequence_row["genome_id"]) != genome_id:
            raise ImportContractError(
                f"Repeat call row references sequence_id {row['sequence_id']!r} outside genome_id {row['genome_id']!r}"
            )
        if str(protein_row["genome_id"]) != genome_id:
            raise ImportContractError(
                f"Repeat call row references protein_id {row['protein_id']!r} outside genome_id {row['genome_id']!r}"
            )
        if str(protein_row["sequence_id"]) != sequence_id:
            raise ImportContractError(
                f"Repeat call row references protein_id {row['protein_id']!r} with mismatched sequence_id {row['sequence_id']!r}"
            )

        retained_sequence_ids.add(sequence_id)
        retained_protein_ids.add(protein_id)

    retained_sequence_rows = [
        row for row in sequence_rows if str(row["sequence_id"]) in retained_sequence_ids
    ]
    retained_protein_rows = [
        row for row in protein_rows if str(row["protein_id"]) in retained_protein_ids
    ]
    return retained_sequence_rows, retained_protein_rows


def _prepare_import_data(batch: ImportBatch, parsed: ParsedPublishedRun) -> PreparedImportData:
    retained_sequence_rows, retained_protein_rows = _select_repeat_linked_rows(
        parsed.genome_rows,
        parsed.sequence_rows,
        parsed.protein_rows,
        parsed.repeat_call_rows,
    )
    _set_batch_state(
        batch,
        phase=ImportPhase.LOADING_FASTA,
        progress_payload={
            "message": "Loading retained CDS and protein FASTA records.",
            "retained_sequences": len(retained_sequence_rows),
            "retained_proteins": len(retained_protein_rows),
        },
    )
    nucleotide_sequences_by_id, amino_acid_sequences_by_id = _load_retained_sequence_content(
        parsed,
        retained_sequence_rows=retained_sequence_rows,
        retained_protein_rows=retained_protein_rows,
    )
    return PreparedImportData(
        retained_sequence_rows=retained_sequence_rows,
        retained_protein_rows=retained_protein_rows,
        nucleotide_sequences_by_id=nucleotide_sequences_by_id,
        amino_acid_sequences_by_id=amino_acid_sequences_by_id,
        analyzed_protein_counts=_count_rows_by_key(parsed.protein_rows, "genome_id"),
        repeat_call_counts_by_protein=_count_rows_by_key(parsed.repeat_call_rows, "protein_id"),
    )


def _load_retained_sequence_content(
    parsed: ParsedPublishedRun,
    *,
    retained_sequence_rows: list[dict[str, object]],
    retained_protein_rows: list[dict[str, object]],
) -> tuple[dict[str, str], dict[str, str]]:
    retained_sequence_ids = {str(row["sequence_id"]) for row in retained_sequence_rows}
    retained_protein_ids = {str(row["protein_id"]) for row in retained_protein_rows}
    nucleotide_sequences_by_id: dict[str, str] = {}
    amino_acid_sequences_by_id: dict[str, str] = {}

    for batch_paths in parsed.artifact_paths.acquisition_batches:
        nucleotide_sequences_by_id.update(
            _read_fasta_subset(
                batch_paths.cds_fna,
                retained_sequence_ids,
                existing_records=nucleotide_sequences_by_id,
                label="CDS",
            )
        )
        amino_acid_sequences_by_id.update(
            _read_fasta_subset(
                batch_paths.proteins_faa,
                retained_protein_ids,
                existing_records=amino_acid_sequences_by_id,
                label="protein",
            )
        )

    missing_sequence_ids = sorted(retained_sequence_ids - set(nucleotide_sequences_by_id))
    if missing_sequence_ids:
        preview = ", ".join(missing_sequence_ids[:5])
        raise ImportContractError(
            f"Missing CDS FASTA records for retained sequence IDs: {preview}"
        )

    missing_protein_ids = sorted(retained_protein_ids - set(amino_acid_sequences_by_id))
    if missing_protein_ids:
        preview = ", ".join(missing_protein_ids[:5])
        raise ImportContractError(
            f"Missing protein FASTA records for retained protein IDs: {preview}"
        )

    return nucleotide_sequences_by_id, amino_acid_sequences_by_id


def _read_fasta_subset(
    path: Path,
    retained_ids: set[str],
    *,
    existing_records: dict[str, str],
    label: str,
) -> dict[str, str]:
    records: dict[str, str] = {}
    current_record_id = ""
    current_chunks: list[str] = []

    def store_current_record() -> None:
        if not current_record_id or current_record_id not in retained_ids:
            return
        sequence_value = "".join(current_chunks).strip()
        existing_value = existing_records.get(current_record_id, records.get(current_record_id))
        if existing_value is not None and existing_value != sequence_value:
            raise ImportContractError(
                f"Conflicting duplicate {label} FASTA records were found for {current_record_id!r}"
            )
        records[current_record_id] = sequence_value

    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                store_current_record()
                current_record_id = line[1:].split()[0]
                current_chunks = []
                continue
            if not current_record_id:
                raise ImportContractError(f"{path} contains FASTA sequence data before the first header")
            current_chunks.append(line)

    store_current_record()
    return records


def _count_rows_by_key(rows: list[dict[str, object]], key_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row[key_name])
        counts[key] = counts.get(key, 0) + 1
    return counts
