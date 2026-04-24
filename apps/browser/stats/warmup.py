"""Bundle builder registry and scope helpers for cache pre-warming.

Used by apps/browser/tasks.py to dispatch and execute PayloadBuild warmup
jobs on the payload_graph Celery queue after a successful import.
"""
from __future__ import annotations

import hashlib
import json

from .params import DEFAULT_MIN_COUNT, DEFAULT_TOP_N, DEFAULT_UNSCOPED_RANK


# Build types that are pre-warmed after every successful import.
# These are the four main bundle families that drive the stats explorer pages.
# All use the default global unfiltered scope (no run, no branch filter).
WARMUP_BUILD_TYPES: frozenset[str] = frozenset([
    "ranked_length_summary",
    "length_profile_vector",
    "ranked_codon_composition_summary",
    "codon_length_composition",
])


def get_bundle_builders() -> dict[str, object]:
    """Return the mapping of build_type → bundle builder function.

    Lazy import to break the import cycle: warmup ← tasks ← queries.
    """
    from .queries import (
        build_codon_length_composition_bundle,
        build_length_profile_vector_bundle,
        build_ranked_codon_composition_summary_bundle,
        build_ranked_length_summary_bundle,
    )

    return {
        "ranked_length_summary": build_ranked_length_summary_bundle,
        "length_profile_vector": build_length_profile_vector_bundle,
        "ranked_codon_composition_summary": build_ranked_codon_composition_summary_bundle,
        "codon_length_composition": build_codon_length_composition_bundle,
    }


def default_warmup_scope_params() -> dict:
    """Return the filter param dict for the global unfiltered default scope.

    Matches the structure of StatsFilterState.cache_key_data() (without
    catalog_version). The default scope is the most commonly requested state:
    no run filter, no branch filter, default rank, default observation thresholds.
    """
    return {
        "run": "",
        "branch": "",
        "branch_q": "",
        "rank": DEFAULT_UNSCOPED_RANK,
        "q": "",
        "method": "",
        "residue": "",
        "length_min": None,
        "length_max": None,
        "purity_min": None,
        "purity_max": None,
        "min_count": DEFAULT_MIN_COUNT,
        "top_n": DEFAULT_TOP_N,
    }


def compute_scope_key(scope_params: dict) -> str:
    """Return a stable SHA1 hash of scope_params for use as PayloadBuild.scope_key."""
    payload = json.dumps(scope_params, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()
