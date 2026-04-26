from __future__ import annotations

from pathlib import Path

from .contracts import (
    ImportContractError,
    V2ArtifactPaths,
)


def resolve_v2_artifacts(publish_root: Path | str) -> V2ArtifactPaths:
    root = Path(publish_root).resolve()
    if not root.is_dir():
        raise ImportContractError(f"Publish root does not exist or is not a directory: {root}")

    paths = V2ArtifactPaths(
        publish_root=root,
        manifest=root / "metadata" / "run_manifest.json",
        repeat_calls_tsv=root / "calls" / "repeat_calls.tsv",
        run_params_tsv=root / "calls" / "run_params.tsv",
        genomes_tsv=root / "tables" / "genomes.tsv",
        taxonomy_tsv=root / "tables" / "taxonomy.tsv",
        matched_sequences_tsv=root / "tables" / "matched_sequences.tsv",
        matched_proteins_tsv=root / "tables" / "matched_proteins.tsv",
        repeat_call_codon_usage_tsv=root / "tables" / "repeat_call_codon_usage.tsv",
        repeat_context_tsv=root / "tables" / "repeat_context.tsv",
        download_manifest_tsv=root / "tables" / "download_manifest.tsv",
        normalization_warnings_tsv=root / "tables" / "normalization_warnings.tsv",
        accession_status_tsv=root / "tables" / "accession_status.tsv",
        accession_call_counts_tsv=root / "tables" / "accession_call_counts.tsv",
        status_summary_json=root / "summaries" / "status_summary.json",
        acquisition_validation_json=root / "summaries" / "acquisition_validation.json",
    )
    for label, path in paths.__dict__.items():
        if label == "publish_root":
            continue
        if not path.is_file():
            raise ImportContractError(f"Required import artifact is missing: {path}")
    return paths
