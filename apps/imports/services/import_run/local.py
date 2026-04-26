from __future__ import annotations

from collections import Counter

from apps.browser.models.genomes import Genome, Protein, Sequence
from apps.browser.models.operations import DownloadManifestEntry, NormalizationWarning
from apps.browser.models.repeat_calls import RepeatCall, RepeatCallCodonUsage, RepeatCallContext
from apps.browser.models.runs import AcquisitionBatch, PipelineRun
from apps.browser.models.taxonomy import Taxon
from apps.imports.models import ImportBatch
from apps.imports.services.published_run import (
    ImportContractError,
    InspectedPublishedRun,
    V2ArtifactPaths,
    iter_accession_call_count_rows,
    iter_accession_status_rows,
    iter_codon_usage_rows,
    iter_matched_protein_rows,
    iter_matched_sequence_rows,
    iter_repeat_context_rows,
    iter_repeat_call_rows,
    iter_run_level_download_manifest_rows,
    iter_run_level_genome_rows,
    iter_run_level_normalization_warning_rows,
    iter_run_parameter_rows,
)

from .entities import _parse_codon_ratio_value
from .operational import (
    _create_accession_call_count_rows_streamed,
    _create_accession_status_rows_streamed,
    _create_run_parameters_streamed,
)
from .orchestrator import _upsert_pipeline_run
from .state import ImportPhase, _ImportBatchStateReporter, _set_batch_state
from .taxonomy import _load_taxonomy_rows, _rebuild_taxon_closure, _upsert_taxa


def _import_inspected_run_local(
    batch: ImportBatch,
    inspected: InspectedPublishedRun,
    *,
    replace_existing: bool,
    reporter: _ImportBatchStateReporter | None = None,
) -> tuple[PipelineRun, dict[str, int]]:
    """Small-fixture v2 importer for SQLite/local tests.

    Production-sized v2 imports use PostgreSQL COPY staging. This path keeps the
    local test suite useful without reintroducing legacy v1 artifact support.
    """

    paths = inspected.artifact_paths
    if not isinstance(paths, V2ArtifactPaths):
        raise ImportContractError("Publish contract v2 importer received non-v2 artifact paths.")

    pipeline_run = _upsert_pipeline_run(inspected.pipeline_run, replace_existing=replace_existing)

    _set_batch_state(
        batch,
        phase=ImportPhase.STAGING,
        progress_payload={"message": "Staging v2 run-level tables locally."},
        reporter=reporter,
        force=True,
    )
    taxonomy_rows = _load_taxonomy_rows(inspected)
    _upsert_taxa(taxonomy_rows)
    _rebuild_taxon_closure()

    batch_ids = _collect_v2_batch_ids(paths)
    if not batch_ids:
        raise ImportContractError("No acquisition batch IDs were found in v2 tables.")
    AcquisitionBatch.objects.bulk_create(
        [AcquisitionBatch(pipeline_run=pipeline_run, batch_id=batch_id) for batch_id in sorted(batch_ids)]
    )
    batch_by_batch_id = {
        item.batch_id: item
        for item in AcquisitionBatch.objects.filter(pipeline_run=pipeline_run).only("id", "batch_id")
    }

    _set_batch_state(
        batch,
        phase=ImportPhase.IMPORTING,
        progress_payload={"message": "Importing v2 rows locally."},
        reporter=reporter,
        force=True,
    )

    run_parameter_count = _create_run_parameters_streamed(
        pipeline_run,
        iter_run_parameter_rows(paths.run_params_tsv),
    )
    genome_count = _create_genomes(pipeline_run, paths, batch_by_batch_id)
    sequence_count = _create_sequences(pipeline_run, paths)
    protein_count = _create_proteins(pipeline_run, paths)
    _update_genome_analyzed_protein_counts(pipeline_run)
    download_manifest_count = _create_download_manifest_entries(pipeline_run, paths, batch_by_batch_id)
    normalization_warning_count = _create_normalization_warnings(pipeline_run, paths, batch_by_batch_id)
    repeat_call_count = _create_repeat_calls(pipeline_run, paths)
    repeat_call_context_count = _create_repeat_call_contexts(pipeline_run, paths)
    repeat_call_codon_usage_count = _create_repeat_call_codon_usages(pipeline_run, paths)
    accession_status_count = _create_accession_status_rows_streamed(
        pipeline_run,
        iter_accession_status_rows(paths.accession_status_tsv),
        batch_by_batch_id,
    )
    accession_call_count = _create_accession_call_count_rows_streamed(
        pipeline_run,
        iter_accession_call_count_rows(paths.accession_call_counts_tsv),
        batch_by_batch_id,
    )

    return pipeline_run, {
        "acquisition_batches": len(batch_by_batch_id),
        "taxonomy": len(taxonomy_rows),
        "genomes": genome_count,
        "sequences": sequence_count,
        "proteins": protein_count,
        "download_manifest_entries": download_manifest_count,
        "normalization_warnings": normalization_warning_count,
        "accession_status_rows": accession_status_count,
        "accession_call_count_rows": accession_call_count,
        "run_parameters": run_parameter_count,
        "repeat_calls": repeat_call_count,
        "repeat_call_contexts": repeat_call_context_count,
        "repeat_call_codon_usages": repeat_call_codon_usage_count,
    }


def _collect_v2_batch_ids(paths: V2ArtifactPaths) -> set[str]:
    batch_ids: set[str] = set()
    scanners = [
        iter_run_level_genome_rows(paths.genomes_tsv),
        iter_matched_sequence_rows(paths.matched_sequences_tsv),
        iter_matched_protein_rows(paths.matched_proteins_tsv),
        iter_run_level_download_manifest_rows(paths.download_manifest_tsv),
        iter_run_level_normalization_warning_rows(paths.normalization_warnings_tsv),
        iter_accession_status_rows(paths.accession_status_tsv),
        iter_accession_call_count_rows(paths.accession_call_counts_tsv),
    ]
    for rows in scanners:
        for row in rows:
            batch_id = str(row.get("batch_id") or "")
            if batch_id:
                batch_ids.add(batch_id)
    return batch_ids


def _create_genomes(
    pipeline_run: PipelineRun,
    paths: V2ArtifactPaths,
    batch_by_batch_id: dict[str, AcquisitionBatch],
) -> int:
    count = 0
    seen: set[str] = set()
    for row in iter_run_level_genome_rows(paths.genomes_tsv):
        genome_id = str(row["genome_id"])
        if genome_id in seen:
            raise ImportContractError(f"Conflicting duplicate genome rows were found for genome_id={genome_id!r}")
        seen.add(genome_id)
        batch = _require_batch(row["batch_id"], batch_by_batch_id, "genome")
        taxon = _require_taxon(row["taxon_id"], "genome")
        Genome.objects.create(
            pipeline_run=pipeline_run,
            batch=batch,
            genome_id=genome_id,
            source=str(row["source"]),
            accession=str(row["accession"]),
            genome_name=str(row["genome_name"]),
            assembly_type=str(row["assembly_type"]),
            taxon=taxon,
            assembly_level=str(row.get("assembly_level", "")),
            species_name=str(row.get("species_name", "")),
            notes=str(row.get("notes", "")),
        )
        count += 1
    return count


def _create_sequences(pipeline_run: PipelineRun, paths: V2ArtifactPaths) -> int:
    genomes = {item.genome_id: item for item in Genome.objects.filter(pipeline_run=pipeline_run)}
    count = 0
    seen: set[str] = set()
    for row in iter_matched_sequence_rows(paths.matched_sequences_tsv):
        sequence_id = str(row["sequence_id"])
        if sequence_id in seen:
            raise ImportContractError(
                f"Conflicting duplicate matched sequence rows were found for sequence_id={sequence_id!r}"
            )
        seen.add(sequence_id)
        genome = _require_mapping_value(genomes, row["genome_id"], "sequence", "genome_id")
        taxon = _require_taxon(row.get("taxon_id") or genome.taxon_id, "sequence")
        Sequence.objects.create(
            pipeline_run=pipeline_run,
            genome=genome,
            taxon=taxon,
            sequence_id=sequence_id,
            sequence_name=str(row["sequence_name"]),
            sequence_length=int(row["sequence_length"]),
            nucleotide_sequence=str(row["nucleotide_sequence"]),
            gene_symbol=str(row.get("gene_symbol", "")),
            transcript_id=str(row.get("transcript_id", "")),
            isoform_id=str(row.get("isoform_id", "")),
            assembly_accession=str(row.get("assembly_accession", "")),
            source_record_id=str(row.get("source_record_id", "")),
            protein_external_id=str(row.get("protein_external_id", "")),
            translation_table=str(row.get("translation_table", "")),
            gene_group=str(row.get("gene_group", "")),
            linkage_status=str(row.get("linkage_status", "")),
            partial_status=str(row.get("partial_status", "")),
        )
        count += 1
    return count


def _create_proteins(pipeline_run: PipelineRun, paths: V2ArtifactPaths) -> int:
    genomes = {item.genome_id: item for item in Genome.objects.filter(pipeline_run=pipeline_run)}
    sequences = {item.sequence_id: item for item in Sequence.objects.filter(pipeline_run=pipeline_run)}
    repeat_counts = Counter(
        str(row["protein_id"])
        for row in iter_repeat_call_rows(paths.repeat_calls_tsv)
    )
    count = 0
    seen: set[str] = set()
    for row in iter_matched_protein_rows(paths.matched_proteins_tsv):
        protein_id = str(row["protein_id"])
        if protein_id in seen:
            raise ImportContractError(
                f"Conflicting duplicate matched protein rows were found for protein_id={protein_id!r}"
            )
        seen.add(protein_id)
        genome = _require_mapping_value(genomes, row["genome_id"], "protein", "genome_id")
        sequence = _require_mapping_value(sequences, row["sequence_id"], "protein", "sequence_id")
        taxon = _require_taxon(row.get("taxon_id") or genome.taxon_id, "protein")
        Protein.objects.create(
            pipeline_run=pipeline_run,
            genome=genome,
            sequence=sequence,
            taxon=taxon,
            protein_id=protein_id,
            protein_name=str(row["protein_name"]),
            protein_length=int(row["protein_length"]),
            accession=genome.accession,
            amino_acid_sequence=str(row["amino_acid_sequence"]),
            gene_symbol=str(row.get("gene_symbol", "")),
            translation_method=str(row.get("translation_method", "")),
            translation_status=str(row.get("translation_status", "")),
            assembly_accession=str(row.get("assembly_accession", "")),
            gene_group=str(row.get("gene_group", "")),
            protein_external_id=str(row.get("protein_external_id", "")),
            repeat_call_count=repeat_counts[str(row["protein_id"])],
        )
        count += 1
    return count


def _update_genome_analyzed_protein_counts(pipeline_run: PipelineRun) -> None:
    for genome in Genome.objects.filter(pipeline_run=pipeline_run):
        genome.analyzed_protein_count = Protein.objects.filter(pipeline_run=pipeline_run, genome=genome).count()
        genome.save(update_fields=["analyzed_protein_count"])


def _create_download_manifest_entries(
    pipeline_run: PipelineRun,
    paths: V2ArtifactPaths,
    batch_by_batch_id: dict[str, AcquisitionBatch],
) -> int:
    count = 0
    for row in iter_run_level_download_manifest_rows(paths.download_manifest_tsv):
        batch = _require_batch(row["batch_id"], batch_by_batch_id, "download manifest")
        DownloadManifestEntry.objects.create(
            pipeline_run=pipeline_run,
            batch=batch,
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
        count += 1
    return count


def _create_normalization_warnings(
    pipeline_run: PipelineRun,
    paths: V2ArtifactPaths,
    batch_by_batch_id: dict[str, AcquisitionBatch],
) -> int:
    count = 0
    for row in iter_run_level_normalization_warning_rows(paths.normalization_warnings_tsv):
        batch = _require_batch(row["batch_id"], batch_by_batch_id, "normalization warning")
        NormalizationWarning.objects.create(
            pipeline_run=pipeline_run,
            batch=batch,
            warning_code=str(row["warning_code"]),
            warning_scope=str(row.get("warning_scope", "")),
            warning_message=str(row.get("warning_message", "")),
            genome_id=str(row.get("genome_id", "")),
            sequence_id=str(row.get("sequence_id", "")),
            protein_id=str(row.get("protein_id", "")),
            assembly_accession=str(row.get("assembly_accession", "")),
            source_file=str(row.get("source_file", "")),
            source_record_id=str(row.get("source_record_id", "")),
        )
        count += 1
    return count


def _create_repeat_calls(pipeline_run: PipelineRun, paths: V2ArtifactPaths) -> int:
    genomes = {item.genome_id: item for item in Genome.objects.filter(pipeline_run=pipeline_run)}
    sequences = {item.sequence_id: item for item in Sequence.objects.filter(pipeline_run=pipeline_run)}
    proteins = {item.protein_id: item for item in Protein.objects.filter(pipeline_run=pipeline_run)}
    count = 0
    for row in iter_repeat_call_rows(paths.repeat_calls_tsv):
        genome = _require_mapping_value(genomes, row["genome_id"], "repeat call", "genome_id")
        sequence = _require_mapping_value(sequences, row["sequence_id"], "repeat call", "sequence_id")
        protein = _require_mapping_value(proteins, row["protein_id"], "repeat call", "protein_id")
        taxon = _require_taxon(row["taxon_id"], "repeat call")
        RepeatCall.objects.create(
            pipeline_run=pipeline_run,
            genome=genome,
            sequence=sequence,
            protein=protein,
            taxon=taxon,
            call_id=str(row["call_id"]),
            method=str(row["method"]),
            accession=genome.accession,
            gene_symbol=protein.gene_symbol,
            protein_name=protein.protein_name,
            protein_length=protein.protein_length,
            start=int(row["start"]),
            end=int(row["end"]),
            length=int(row["length"]),
            repeat_residue=str(row["repeat_residue"]),
            repeat_count=int(row["repeat_count"]),
            non_repeat_count=int(row["non_repeat_count"]),
            purity=float(row["purity"]),
            aa_sequence=str(row["aa_sequence"]),
            codon_sequence=str(row.get("codon_sequence", "")),
            codon_metric_name=str(row.get("codon_metric_name", "")),
            codon_metric_value=str(row.get("codon_metric_value", "")),
            codon_ratio_value=_parse_codon_ratio_value(row.get("codon_metric_value")),
            window_definition=str(row.get("window_definition", "")),
            template_name=str(row.get("template_name", "")),
            merge_rule=str(row.get("merge_rule", "")),
            score=str(row.get("score", "")),
        )
        count += 1
    return count


def _create_repeat_call_contexts(pipeline_run: PipelineRun, paths: V2ArtifactPaths) -> int:
    repeat_calls = {item.call_id: item for item in RepeatCall.objects.filter(pipeline_run=pipeline_run)}
    count = 0
    for row in iter_repeat_context_rows(paths.repeat_context_tsv):
        repeat_call = _require_mapping_value(repeat_calls, row["call_id"], "repeat context", "call_id")
        if repeat_call.sequence.sequence_id != row["sequence_id"] or repeat_call.protein.protein_id != row["protein_id"]:
            raise ImportContractError("Repeat context row does not match its repeat call sequence/protein IDs.")
        RepeatCallContext.objects.create(
            repeat_call=repeat_call,
            pipeline_run=pipeline_run,
            protein_id=str(row["protein_id"]),
            sequence_id=str(row["sequence_id"]),
            aa_left_flank=str(row.get("aa_left_flank", "")),
            aa_right_flank=str(row.get("aa_right_flank", "")),
            nt_left_flank=str(row.get("nt_left_flank", "")),
            nt_right_flank=str(row.get("nt_right_flank", "")),
            aa_context_window_size=int(row["aa_context_window_size"]),
            nt_context_window_size=int(row["nt_context_window_size"]),
        )
        count += 1
    return count


def _create_repeat_call_codon_usages(pipeline_run: PipelineRun, paths: V2ArtifactPaths) -> int:
    repeat_calls = {item.call_id: item for item in RepeatCall.objects.filter(pipeline_run=pipeline_run)}
    count = 0
    for row in iter_codon_usage_rows(paths.repeat_call_codon_usage_tsv):
        repeat_call = _require_mapping_value(repeat_calls, row["call_id"], "codon usage", "call_id")
        if (
            repeat_call.method != row["method"]
            or repeat_call.repeat_residue != row["repeat_residue"]
            or repeat_call.sequence.sequence_id != row["sequence_id"]
            or repeat_call.protein.protein_id != row["protein_id"]
        ):
            raise ImportContractError("Codon usage row does not match its repeat call method/residue/entities.")
        RepeatCallCodonUsage.objects.create(
            repeat_call=repeat_call,
            amino_acid=str(row["amino_acid"]),
            codon=str(row["codon"]),
            codon_count=int(row["codon_count"]),
            codon_fraction=float(row["codon_fraction"]),
        )
        count += 1
    return count


def _require_batch(
    batch_id: object,
    batch_by_batch_id: dict[str, AcquisitionBatch],
    label: str,
) -> AcquisitionBatch:
    key = str(batch_id or "")
    batch = batch_by_batch_id.get(key)
    if batch is None:
        raise ImportContractError(f"{label.capitalize()} row references missing batch_id {batch_id!r}")
    return batch


def _require_taxon(taxon_id: object, label: str) -> Taxon:
    try:
        return Taxon.objects.get(taxon_id=int(taxon_id))
    except (Taxon.DoesNotExist, TypeError, ValueError) as exc:
        raise ImportContractError(f"{label.capitalize()} row references missing taxon_id {taxon_id!r}") from exc


def _require_mapping_value(mapping: dict[str, object], key: object, label: str, field_name: str):
    normalized = str(key or "")
    value = mapping.get(normalized)
    if value is None:
        raise ImportContractError(f"{label.capitalize()} row references missing {field_name} {key!r}")
    return value
