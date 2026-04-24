"""Download service boundary: classification policy and build-state helpers.

All current download exports are classified as SYNC (inline-streamed via
BrowserTSVExportMixin / StatsTSVExportMixin). This module is the single place
that governs whether a given download type goes through the inline path or the
async artifact path (Phase 6).

To promote a type to async+persisted:
  1. Add it to _ASYNC_ARTIFACT_TYPES below.
  2. Implement the corresponding Celery task on the 'downloads' queue.
  3. Wire the task dispatch in the view using get_or_create_download_build().
  4. Add frontend polling against the /browser/downloads/<pk>/status/ endpoint.
"""

from __future__ import annotations

from enum import StrEnum


class DownloadClassification(StrEnum):
    SYNC = "sync"
    ASYNC_ARTIFACT = "async+persisted"


class DownloadBuildType(StrEnum):
    """Canonical identifiers for every download type in the browser.

    List-page exports use the BrowserTSVExportMixin.
    Stats exports use the StatsTSVExportMixin dataset_key convention.
    """

    # List-page exports
    RUN_LIST = "run_list"
    ACCESSION_LIST = "accession_list"
    GENOME_LIST = "genome_list"
    SEQUENCE_LIST = "sequence_list"
    REPEAT_CALL_LIST = "repeat_call_list"

    # Stats: repeat lengths
    LENGTH_SUMMARY = "length.summary"
    LENGTH_OVERVIEW_TYPICAL = "length.overview_typical"
    LENGTH_OVERVIEW_TAIL = "length.overview_tail"
    LENGTH_INSPECT = "length.inspect"

    # Stats: codon composition (ratios)
    CODON_RATIO_SUMMARY = "codon_ratio.summary"
    CODON_RATIO_OVERVIEW = "codon_ratio.overview"
    CODON_RATIO_BROWSE = "codon_ratio.browse"
    CODON_RATIO_INSPECT = "codon_ratio.inspect"

    # Stats: codon composition by length
    CODON_LENGTH_SUMMARY = "codon_length.summary"
    CODON_LENGTH_PREFERENCE = "codon_length.preference"
    CODON_LENGTH_DOMINANCE = "codon_length.dominance"
    CODON_LENGTH_SHIFT = "codon_length.shift"
    CODON_LENGTH_SIMILARITY = "codon_length.similarity"
    CODON_LENGTH_BROWSE = "codon_length.browse"
    CODON_LENGTH_INSPECT = "codon_length.inspect"
    CODON_LENGTH_COMPARISON = "codon_length.comparison"


# Promote types here once timing data from Phase 4 instrumentation justifies it.
# Until then keep this empty so all requests stay on the fast inline path.
_ASYNC_ARTIFACT_TYPES: frozenset[DownloadBuildType] = frozenset()


def classify_download(build_type: DownloadBuildType) -> DownloadClassification:
    """Return the execution classification for the given download type.

    SYNC     → stream inline from Django (current behaviour for all types).
    ASYNC_ARTIFACT → create a DownloadBuild record and enqueue a Celery task;
                     the client polls /browser/downloads/<pk>/status/ until ready.
    """
    if build_type in _ASYNC_ARTIFACT_TYPES:
        return DownloadClassification.ASYNC_ARTIFACT
    return DownloadClassification.SYNC


def get_or_create_download_build(
    build_type: DownloadBuildType,
    scope_key: str,
    catalog_version: int,
    *,
    requested_by=None,
):
    """Return an existing ready/pending DownloadBuild or create a new one.

    Only call this for ASYNC_ARTIFACT-classified types. The caller is
    responsible for enqueueing the Celery task when a new build is created.

    Returns (build, created): created is True when a new PENDING build was
    created, False when an existing non-terminal build was reused.
    """
    from apps.browser.models import DownloadBuild

    existing = (
        DownloadBuild.objects.filter(
            build_type=build_type,
            scope_key=scope_key,
            catalog_version=catalog_version,
            status__in=[DownloadBuild.Status.PENDING, DownloadBuild.Status.BUILDING, DownloadBuild.Status.READY],
        )
        .order_by("-created_at")
        .first()
    )
    if existing is not None:
        return existing, False

    build = DownloadBuild.objects.create(
        build_type=build_type,
        scope_key=scope_key,
        catalog_version=catalog_version,
        status=DownloadBuild.Status.PENDING,
        requested_by=requested_by,
    )
    return build, True
