from __future__ import annotations

from pathlib import Path

from .contracts import BatchArtifactPaths, ImportContractError, RequiredArtifactPaths


def resolve_required_artifacts(publish_root: Path | str) -> RequiredArtifactPaths:
    root = Path(publish_root).resolve()
    if not root.is_dir():
        raise ImportContractError(f"Publish root does not exist or is not a directory: {root}")

    paths = RequiredArtifactPaths(
        publish_root=root,
        manifest=root / "metadata" / "run_manifest.json",
        acquisition_batches_root=root / "acquisition" / "batches",
        acquisition_batches=(),
        accession_status_tsv=root / "status" / "accession_status.tsv",
        accession_call_counts_tsv=root / "status" / "accession_call_counts.tsv",
        run_params_tsv=root / "calls" / "run_params.tsv",
        repeat_calls_tsv=root / "calls" / "repeat_calls.tsv",
    )
    for label, path in paths.__dict__.items():
        if label in {"publish_root", "acquisition_batches_root", "acquisition_batches"}:
            continue
        if not path.is_file():
            raise ImportContractError(f"Required import artifact is missing: {path}")
    return paths


def _resolve_batch_artifacts(artifact_paths: RequiredArtifactPaths) -> tuple[BatchArtifactPaths, ...]:
    batches_root = artifact_paths.acquisition_batches_root
    if not batches_root.is_dir():
        raise ImportContractError(f"Required import artifact is missing: {batches_root}")

    batch_paths: list[BatchArtifactPaths] = []
    for batch_root in sorted(path for path in batches_root.iterdir() if path.is_dir()):
        batch_paths.append(
            BatchArtifactPaths(
                batch_id=batch_root.name,
                batch_root=batch_root,
                genomes_tsv=batch_root / "genomes.tsv",
                taxonomy_tsv=batch_root / "taxonomy.tsv",
                sequences_tsv=batch_root / "sequences.tsv",
                proteins_tsv=batch_root / "proteins.tsv",
                cds_fna=batch_root / "cds.fna",
                proteins_faa=batch_root / "proteins.faa",
                download_manifest_tsv=batch_root / "download_manifest.tsv",
                normalization_warnings_tsv=batch_root / "normalization_warnings.tsv",
                acquisition_validation_json=batch_root / "acquisition_validation.json",
            )
        )

    if not batch_paths:
        raise ImportContractError(f"No raw acquisition batches were found under {batches_root}")

    for batch_path in batch_paths:
        for path in (
            batch_path.genomes_tsv,
            batch_path.taxonomy_tsv,
            batch_path.sequences_tsv,
            batch_path.proteins_tsv,
            batch_path.cds_fna,
            batch_path.proteins_faa,
            batch_path.download_manifest_tsv,
            batch_path.normalization_warnings_tsv,
            batch_path.acquisition_validation_json,
        ):
            if not path.is_file():
                raise ImportContractError(f"Required import artifact is missing: {path}")

    return tuple(batch_paths)
