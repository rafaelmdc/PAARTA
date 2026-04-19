from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.models import Count, F, Max, Min, Q, Sum

from ..models import CanonicalRepeatCall, CanonicalRepeatCallCodonUsage
from .aggregates import PercentileCont
from .filters import StatsFilterState
from .ordering import order_taxon_rows_by_lineage
from .summaries import (
    normalize_length_summary_value,
    normalize_numeric_summary_value,
    summarize_ranked_codon_composition_groups,
    summarize_ranked_length_groups,
)


def build_ranked_length_summary_bundle(filter_state: StatsFilterState) -> dict[str, object]:
    cache_key = f"browser:stats:length-summary:{filter_state.cache_key()}"
    cached_bundle = cache.get(cache_key)
    if cached_bundle is not None:
        return cached_bundle

    matching_repeat_calls_count = build_filtered_repeat_call_queryset(filter_state).count()
    total_taxa_count = build_ranked_taxon_group_count(filter_state)
    if connection.vendor == "postgresql":
        summary_rows = list(build_ranked_length_summary_queryset(filter_state))
    else:
        group_rows = list(build_ranked_taxon_group_queryset(filter_state))
        display_taxon_ids = [row["display_taxon_id"] for row in group_rows]
        grouped_lengths = (
            list(
                build_group_length_values_queryset(
                    filter_state,
                    display_taxon_ids=display_taxon_ids,
                )
            )
            if display_taxon_ids
            else []
        )
        summary_rows = summarize_ranked_length_groups(group_rows, grouped_lengths)

    bundle = {
        "matching_repeat_calls_count": matching_repeat_calls_count,
        "summary_rows": summary_rows,
        "total_taxa_count": total_taxa_count,
        "visible_taxa_count": len(summary_rows),
    }
    cache.set(cache_key, bundle, timeout=getattr(settings, "HOMOREPEAT_BROWSER_STATS_CACHE_TTL", 60))
    return bundle


def build_ranked_codon_composition_summary_bundle(filter_state: StatsFilterState) -> dict[str, object]:
    if not filter_state.residue:
        return {
            "matching_repeat_calls_count": 0,
            "summary_rows": [],
            "total_taxa_count": 0,
            "visible_taxa_count": 0,
            "visible_codons": [],
        }

    cache_key = f"browser:stats:codon-composition:{filter_state.cache_key()}"
    cached_bundle = cache.get(cache_key)
    if cached_bundle is not None:
        return cached_bundle

    matching_repeat_calls_count = build_filtered_repeat_call_queryset(filter_state).count()
    total_taxa_count = build_ranked_taxon_group_count(filter_state)
    group_rows = list(build_ranked_taxon_group_queryset(filter_state))
    display_taxon_ids = [row["display_taxon_id"] for row in group_rows]
    grouped_species_call_codon_fractions = (
        list(
            build_group_codon_species_call_fraction_queryset(
                filter_state,
                display_taxon_ids=display_taxon_ids,
            )
        )
        if display_taxon_ids
        else []
    )
    visible_codons = sorted({codon for _, _, _, codon, _ in grouped_species_call_codon_fractions})
    summary_rows = (
        summarize_ranked_codon_composition_groups(
            group_rows,
            grouped_species_call_codon_fractions,
            visible_codons=visible_codons,
        )
        if visible_codons
        else []
    )
    if summary_rows:
        summary_rows = order_taxon_rows_by_lineage(summary_rows)

    bundle = {
        "matching_repeat_calls_count": matching_repeat_calls_count,
        "summary_rows": summary_rows,
        "total_taxa_count": total_taxa_count,
        "visible_taxa_count": len(summary_rows),
        "visible_codons": visible_codons,
    }
    cache.set(cache_key, bundle, timeout=getattr(settings, "HOMOREPEAT_BROWSER_STATS_CACHE_TTL", 60))
    return bundle


def build_codon_composition_inspect_bundle(filter_state: StatsFilterState) -> dict[str, object]:
    if not filter_state.residue:
        return {
            "observation_count": 0,
            "visible_codons": [],
            "codon_shares": [],
        }

    cache_key = f"browser:stats:codon-composition-inspect:{filter_state.cache_key()}"
    cached_bundle = cache.get(cache_key)
    if cached_bundle is not None:
        return cached_bundle

    observation_count = build_filtered_repeat_call_queryset(filter_state).count()
    codon_fraction_sums = list(
        build_filtered_codon_usage_queryset(filter_state)
        .values("codon")
        .annotate(total_fraction=Sum("codon_fraction"))
        .order_by("codon")
        .values_list("codon", "total_fraction")
    )
    visible_codons = [codon for codon, _ in codon_fraction_sums]
    codon_shares = (
        [
            {
                "codon": codon,
                "share": normalize_numeric_summary_value(float(total_fraction) / observation_count),
            }
            for codon, total_fraction in codon_fraction_sums
        ]
        if observation_count > 0
        else []
    )
    bundle = {
        "observation_count": observation_count,
        "visible_codons": visible_codons,
        "codon_shares": codon_shares,
    }
    cache.set(cache_key, bundle, timeout=getattr(settings, "HOMOREPEAT_BROWSER_STATS_CACHE_TTL", 60))
    return bundle


def build_filtered_repeat_call_queryset(filter_state: StatsFilterState):
    queryset = CanonicalRepeatCall.objects.order_by()

    if filter_state.current_run is not None:
        queryset = queryset.filter(latest_pipeline_run=filter_state.current_run)
    if filter_state.branch_taxa_ids is not None:
        queryset = queryset.filter(taxon_id__in=filter_state.branch_taxa_ids)
    if filter_state.q:
        queryset = queryset.filter(
            Q(gene_symbol__istartswith=filter_state.q)
            | Q(protein__protein_id__istartswith=filter_state.q)
            | Q(protein_name__istartswith=filter_state.q)
            | Q(accession__istartswith=filter_state.q)
        )
    if filter_state.method:
        queryset = queryset.filter(method=filter_state.method)
    if filter_state.residue:
        queryset = queryset.filter(repeat_residue=filter_state.residue)
    if filter_state.length_min is not None:
        queryset = queryset.filter(length__gte=filter_state.length_min)
    if filter_state.length_max is not None:
        queryset = queryset.filter(length__lte=filter_state.length_max)
    if filter_state.purity_min is not None:
        queryset = queryset.filter(purity__gte=filter_state.purity_min)
    if filter_state.purity_max is not None:
        queryset = queryset.filter(purity__lte=filter_state.purity_max)

    return queryset


def build_filtered_codon_usage_queryset(filter_state: StatsFilterState):
    if not filter_state.residue:
        return CanonicalRepeatCallCodonUsage.objects.none()

    return CanonicalRepeatCallCodonUsage.objects.order_by().filter(
        repeat_call__in=build_filtered_repeat_call_queryset(filter_state),
        amino_acid=filter_state.residue,
    )


def build_ranked_taxon_group_queryset(filter_state: StatsFilterState):
    return build_ranked_taxon_group_base_queryset(
        filter_state,
    ).order_by(
        "-observation_count",
        "display_taxon_name",
        "display_taxon_id",
    )[: filter_state.top_n]


def build_ranked_taxon_group_count(filter_state: StatsFilterState) -> int:
    return build_ranked_taxon_group_base_queryset(
        filter_state,
    ).count()


def build_group_length_values_queryset(filter_state: StatsFilterState, *, display_taxon_ids):
    return (
        _with_display_taxon_annotations(
            build_filtered_repeat_call_queryset(filter_state),
            rank=filter_state.rank,
        )
        .filter(display_taxon_id__in=display_taxon_ids)
        .values_list("display_taxon_id", "length")
        .order_by("display_taxon_id", "length")
    )


def build_group_codon_species_call_fraction_queryset(filter_state: StatsFilterState, *, display_taxon_ids):
    return (
        _with_display_taxon_annotations(
            build_filtered_codon_usage_queryset(filter_state),
            rank=filter_state.rank,
            taxon_field_name="repeat_call__taxon",
        )
        .filter(display_taxon_id__in=display_taxon_ids)
        .values_list(
            "display_taxon_id",
            "repeat_call__taxon_id",
            "repeat_call_id",
            "codon",
            "codon_fraction",
        )
        .order_by("display_taxon_id", "repeat_call__taxon_id", "repeat_call_id", "codon")
    )


def build_ranked_length_summary_queryset(filter_state: StatsFilterState):
    queryset = _with_display_taxon_annotations(
        build_filtered_repeat_call_queryset(filter_state),
        rank=filter_state.rank,
    ).exclude(display_taxon_id__isnull=True)

    summary_rows = (
        queryset.values("display_taxon_id", "display_taxon_name", "display_taxon_rank")
        .annotate(
            observation_count=Count("pk"),
            min_length=Min("length"),
            q1=PercentileCont(0.25, "length"),
            median=PercentileCont(0.5, "length"),
            q3=PercentileCont(0.75, "length"),
            max_length=Max("length"),
        )
        .filter(observation_count__gte=filter_state.min_count)
        .order_by("-observation_count", "display_taxon_name", "display_taxon_id")[: filter_state.top_n]
    )

    return [
        {
            "taxon_id": row["display_taxon_id"],
            "taxon_name": row["display_taxon_name"],
            "rank": row["display_taxon_rank"],
            "observation_count": row["observation_count"],
            "min_length": row["min_length"],
            "q1": normalize_length_summary_value(row["q1"]),
            "median": normalize_length_summary_value(row["median"]),
            "q3": normalize_length_summary_value(row["q3"]),
            "max_length": row["max_length"],
        }
        for row in summary_rows
    ]
def build_ranked_taxon_group_base_queryset(filter_state: StatsFilterState):
    queryset = _with_display_taxon_annotations(
        build_filtered_repeat_call_queryset(filter_state),
        rank=filter_state.rank,
    ).exclude(display_taxon_id__isnull=True)

    return (
        queryset.values("display_taxon_id", "display_taxon_name", "display_taxon_rank")
        .annotate(
            observation_count=Count("pk"),
            species_count=Count("taxon_id", distinct=True),
        )
        .filter(observation_count__gte=filter_state.min_count)
    )


def _with_display_taxon_annotations(queryset, *, rank: str, taxon_field_name: str = "taxon"):
    return queryset.filter(
        **{f"{taxon_field_name}__closure_ancestors__ancestor__rank": rank},
    ).annotate(
        display_taxon_id=F(f"{taxon_field_name}__closure_ancestors__ancestor_id"),
        display_taxon_name=F(f"{taxon_field_name}__closure_ancestors__ancestor__taxon_name"),
        display_taxon_rank=F(f"{taxon_field_name}__closure_ancestors__ancestor__rank"),
    )
