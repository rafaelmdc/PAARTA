from __future__ import annotations

from math import isfinite

from apps.browser.models.runs import PipelineRun


def _delete_run_scoped_rows(pipeline_run: PipelineRun) -> None:
    pipeline_run.normalization_warnings.all().delete()
    pipeline_run.download_manifest_entries.all().delete()
    pipeline_run.accession_call_count_rows.all().delete()
    pipeline_run.accession_status_rows.all().delete()
    pipeline_run.run_parameters.all().delete()
    pipeline_run.genomes.all().delete()
    pipeline_run.acquisition_batches.all().delete()


def _parse_codon_ratio_value(raw_value: object) -> float | None:
    if raw_value is None:
        return None

    text = str(raw_value).strip()
    if not text:
        return None

    try:
        parsed = float(text)
    except (TypeError, ValueError):
        return None

    return parsed if isfinite(parsed) else None
