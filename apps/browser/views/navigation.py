from urllib.parse import urlencode

from django.urls import reverse

from ..models import (
    AccessionCallCount,
    AccessionStatus,
    DownloadManifestEntry,
    Genome,
    NormalizationWarning,
    PipelineRun,
    Protein,
    RepeatCall,
    Sequence,
    Taxon,
)


def _url_with_query(base_url: str, **params) -> str:
    cleaned_params = {key: value for key, value in params.items() if value not in ("", None)}
    if not cleaned_params:
        return base_url
    return f"{base_url}?{urlencode(cleaned_params)}"


def _nav_item(title: str, description: str, *, url_name: str, count: int | None = None, **params):
    item = {
        "title": title,
        "description": description,
        "url": _url_with_query(reverse(url_name), **params),
    }
    if count is not None:
        item["count"] = count
    return item


def _browser_directory_sections():
    return [
        {
            "title": "Core browsers",
            "description": "Start with the canonical entity views and then branch into detail pages.",
            "items": [
                _nav_item(
                    "Imported runs",
                    "Run-first entrypoint for provenance, scope, and browser branching.",
                    url_name="browser:run-list",
                    count=PipelineRun.objects.count(),
                ),
                _nav_item(
                    "Taxa",
                    "Lineage-aware taxonomy browser across imported or run-scoped data.",
                    url_name="browser:taxon-list",
                    count=Taxon.objects.count(),
                ),
                _nav_item(
                    "Genomes",
                    "Accession-aware genome rows linked to taxa, runs, proteins, and calls.",
                    url_name="browser:genome-list",
                    count=Genome.objects.count(),
                ),
                _nav_item(
                    "Sequences",
                    "Call-linked sequence subset stored for browsing and provenance.",
                    url_name="browser:sequence-list",
                    count=Sequence.objects.count(),
                ),
                _nav_item(
                    "Proteins",
                    "Repeat-bearing protein records with genome and taxon provenance.",
                    url_name="browser:protein-list",
                    count=Protein.objects.count(),
                ),
                _nav_item(
                    "Repeat calls",
                    "Canonical repeat-call records with direct links back to proteins and genomes.",
                    url_name="browser:repeatcall-list",
                    count=RepeatCall.objects.count(),
                ),
            ],
        },
        {
            "title": "Derived and merged",
            "description": "Use the collapsed cross-run layer when accession-group analysis is the main task.",
            "items": [
                _nav_item(
                    "Merged accession analytics",
                    "Derived accession groups, collapsed calls, and denominator-safe merged percentages.",
                    url_name="browser:accession-list",
                    count=Genome.objects.exclude(accession="").order_by().values("accession").distinct().count(),
                ),
            ],
        },
        {
            "title": "Operational provenance",
            "description": "Raw side-artifact tables for acquisition, normalization, and status inspection.",
            "items": [
                _nav_item(
                    "Accession status",
                    "Run-aware operational ledger for download, detect, finalize, and terminal outcomes.",
                    url_name="browser:accessionstatus-list",
                    count=AccessionStatus.objects.count(),
                ),
                _nav_item(
                    "Method and residue status",
                    "Per-accession method and residue counts emitted by the raw pipeline.",
                    url_name="browser:accessioncallcount-list",
                    count=AccessionCallCount.objects.count(),
                ),
                _nav_item(
                    "Download manifest",
                    "Batch-scoped acquisition provenance retained from imported manifest rows.",
                    url_name="browser:downloadmanifest-list",
                    count=DownloadManifestEntry.objects.count(),
                ),
                _nav_item(
                    "Normalization warnings",
                    "Imported warning rows from raw acquisition and normalization outputs.",
                    url_name="browser:normalizationwarning-list",
                    count=NormalizationWarning.objects.count(),
                ),
            ],
        },
    ]
