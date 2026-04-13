from collections import Counter

from django.db.models import Count, Max, Min, Q
from django.db.models.functions import Trim

from ..models import (
    Genome,
    MergedProteinOccurrence,
    MergedProteinSummary,
    MergedResidueOccurrence,
    MergedResidueSummary,
    RepeatCall,
    Taxon,
)
from .metrics import _counter_summary
from .repeat_calls import _resolved_branch_taxa_ids, materialize_merged_repeat_call_groups


def accession_group_queryset(
    *,
    current_run=None,
    search_query: str = "",
    accession_query: str = "",
    genome_name: str = "",
    branch_taxon: Taxon | None = None,
    branch_taxa_ids=None,
):
    return source_genome_queryset(
        current_run=current_run,
        search_query=search_query,
        accession_query=accession_query,
        genome_name=genome_name,
        branch_taxon=branch_taxon,
        branch_taxa_ids=branch_taxa_ids,
    ).values("accession").annotate(
        source_genomes_count=Count("pk", distinct=True),
        source_runs_count=Count("pipeline_run", distinct=True),
        raw_repeat_calls_count=Count("repeat_calls", distinct=True),
        analyzed_protein_min=Min("analyzed_protein_count"),
        analyzed_protein_max=Max("analyzed_protein_count"),
    )


def build_accession_summary(accession: str) -> dict:
    source_genomes = list(
        Genome.objects.filter(accession=accession)
        .select_related("pipeline_run", "taxon")
        .annotate(
            proteins_count=Count("proteins", distinct=True),
            repeat_calls_count=Count("repeat_calls", distinct=True),
        )
        .order_by("pipeline_run__run_id", "genome_id")
    )
    if not source_genomes:
        raise Genome.DoesNotExist(f"No imported genomes found for accession {accession}.")

    source_runs = {}
    source_taxa = {}
    for genome in source_genomes:
        source_runs[genome.pipeline_run.pk] = genome.pipeline_run
        source_taxa[genome.taxon.pk] = genome.taxon

    source_repeat_calls = RepeatCall.objects.filter(genome__accession=accession)
    source_repeat_calls_count = source_repeat_calls.count()
    included_protein_identity_count = _trusted_protein_identity_repeat_calls(source_repeat_calls).count()
    included_residue_identity_count = _trusted_residue_identity_repeat_calls(source_repeat_calls).count()
    collapsed_repeat_calls_count = MergedResidueSummary.objects.filter(accession=accession).count()
    merged_repeat_bearing_proteins_count = MergedProteinSummary.objects.filter(accession=accession).count()
    analyzed_protein_counts = sorted({genome.analyzed_protein_count for genome in source_genomes})
    merged_analyzed_protein_count = analyzed_protein_counts[0] if len(analyzed_protein_counts) == 1 else None
    repeat_bearing_protein_percentage = None
    if merged_analyzed_protein_count:
        repeat_bearing_protein_percentage = (
            merged_repeat_bearing_proteins_count / merged_analyzed_protein_count
        ) * 100

    collapsed_call_groups = materialize_merged_repeat_call_groups(
        list(
            MergedResidueSummary.objects.filter(accession=accession).order_by(
                "method",
                "protein_name",
                "start",
                "repeat_residue",
                "id",
            )
        )
    )

    return {
        "accession": accession,
        "source_genomes": source_genomes,
        "source_runs": sorted(source_runs.values(), key=lambda run: run.run_id),
        "source_taxa": sorted(source_taxa.values(), key=lambda taxon: (taxon.taxon_name, taxon.taxon_id)),
        "source_genomes_count": len(source_genomes),
        "source_runs_count": len({genome.pipeline_run_id for genome in source_genomes}),
        "source_repeat_calls_count": source_repeat_calls_count,
        "collapsed_repeat_calls_count": collapsed_repeat_calls_count,
        "duplicate_source_repeat_calls_count": included_residue_identity_count - collapsed_repeat_calls_count,
        "excluded_protein_identity_repeat_calls_count": source_repeat_calls_count - included_protein_identity_count,
        "excluded_residue_identity_repeat_calls_count": source_repeat_calls_count - included_residue_identity_count,
        "collapsed_call_groups": collapsed_call_groups,
        "merged_repeat_bearing_proteins_count": merged_repeat_bearing_proteins_count,
        "analyzed_protein_counts": analyzed_protein_counts,
        "merged_analyzed_protein_count": merged_analyzed_protein_count,
        "has_analyzed_protein_conflict": len(analyzed_protein_counts) > 1,
        "repeat_bearing_protein_percentage": repeat_bearing_protein_percentage,
    }


def source_genome_queryset(
    *,
    current_run=None,
    search_query: str = "",
    accession_query: str = "",
    genome_name: str = "",
    branch_taxon: Taxon | None = None,
    branch_taxa_ids=None,
):
    queryset = Genome.objects.exclude(accession="")

    if current_run is not None:
        queryset = queryset.filter(pipeline_run=current_run)

    if search_query:
        queryset = queryset.filter(
            Q(accession__icontains=search_query) | Q(genome_name__icontains=search_query)
        )

    if accession_query:
        queryset = queryset.filter(accession__icontains=accession_query)

    if genome_name:
        queryset = queryset.filter(genome_name__icontains=genome_name)

    resolved_branch_taxa_ids = _resolved_branch_taxa_ids(
        branch_taxon=branch_taxon,
        branch_taxa_ids=branch_taxa_ids,
    )
    if resolved_branch_taxa_ids is not None:
        queryset = queryset.filter(taxon_id__in=resolved_branch_taxa_ids)

    return queryset


def build_accession_analytics(
    *,
    current_run=None,
    search_query: str = "",
    accession_query: str = "",
    genome_name: str = "",
    branch_taxon: Taxon | None = None,
    branch_taxa_ids=None,
):
    accession_groups = list(
        accession_group_queryset(
            current_run=current_run,
            search_query=search_query,
            accession_query=accession_query,
            genome_name=genome_name,
            branch_taxon=branch_taxon,
            branch_taxa_ids=branch_taxa_ids,
        )
    )
    source_genomes = source_genome_queryset(
        current_run=current_run,
        search_query=search_query,
        accession_query=accession_query,
        genome_name=genome_name,
        branch_taxon=branch_taxon,
        branch_taxa_ids=branch_taxa_ids,
    )
    accessions = [group["accession"] for group in accession_groups]
    source_repeat_calls = RepeatCall.objects.filter(genome_id__in=source_genomes.values("pk"))

    proteins_by_accession = _summary_counts_by_accession(
        _scoped_protein_occurrences(
            current_run=current_run,
            branch_taxon=branch_taxon,
            branch_taxa_ids=branch_taxa_ids,
            accessions=accessions,
        )
    )
    collapsed_calls_by_accession = _summary_counts_by_accession(
        _scoped_residue_occurrences(
            current_run=current_run,
            branch_taxon=branch_taxon,
            branch_taxa_ids=branch_taxa_ids,
            accessions=accessions,
        )
    )
    method_summary = _counter_summary(
        _summary_counter(
            _scoped_residue_occurrences(
                current_run=current_run,
                branch_taxon=branch_taxon,
                branch_taxa_ids=branch_taxa_ids,
                accessions=accessions,
            ),
            field_name="summary__method",
        )
    )
    residue_summary = _counter_summary(
        _summary_counter(
            _scoped_residue_occurrences(
                current_run=current_run,
                branch_taxon=branch_taxon,
                branch_taxa_ids=branch_taxa_ids,
                accessions=accessions,
            ),
            field_name="summary__repeat_residue",
        )
    )

    source_repeat_calls_count = source_repeat_calls.count()
    included_protein_by_accession = _raw_counts_by_accession(
        _trusted_protein_identity_repeat_calls(source_repeat_calls)
    )
    included_residue_by_accession = _raw_counts_by_accession(
        _trusted_residue_identity_repeat_calls(source_repeat_calls)
    )
    included_protein_identity_count = sum(included_protein_by_accession.values())
    included_residue_identity_count = sum(included_residue_by_accession.values())

    safe_accessions = {
        group["accession"]
        for group in accession_groups
        if group["analyzed_protein_min"] == group["analyzed_protein_max"]
    }
    analyzed_proteins_total = sum(
        group["analyzed_protein_min"]
        for group in accession_groups
        if group["accession"] in safe_accessions
    )
    safe_repeat_bearing_proteins_count = sum(
        proteins_by_accession.get(accession, 0) for accession in safe_accessions
    )
    repeat_bearing_protein_percentage = None
    if analyzed_proteins_total:
        repeat_bearing_protein_percentage = (
            safe_repeat_bearing_proteins_count / analyzed_proteins_total
        ) * 100

    accession_metrics = {}
    for group in accession_groups:
        accession = group["accession"]
        raw_repeat_calls_count = group["raw_repeat_calls_count"]
        has_analyzed_protein_conflict = group["analyzed_protein_min"] != group["analyzed_protein_max"]
        merged_analyzed_protein_count = None if has_analyzed_protein_conflict else group["analyzed_protein_min"]
        merged_repeat_bearing_proteins_count = proteins_by_accession.get(accession, 0)
        collapsed_repeat_calls_count = collapsed_calls_by_accession.get(accession, 0)
        accession_percentage = None
        if merged_analyzed_protein_count:
            accession_percentage = (
                merged_repeat_bearing_proteins_count / merged_analyzed_protein_count
            ) * 100

        accession_metrics[accession] = {
            "has_analyzed_protein_conflict": has_analyzed_protein_conflict,
            "collapsed_repeat_calls_count": collapsed_repeat_calls_count,
            "duplicate_source_repeat_calls_count": (
                included_residue_by_accession.get(accession, 0) - collapsed_repeat_calls_count
            ),
            "excluded_protein_identity_repeat_calls_count": (
                raw_repeat_calls_count - included_protein_by_accession.get(accession, 0)
            ),
            "excluded_residue_identity_repeat_calls_count": (
                raw_repeat_calls_count - included_residue_by_accession.get(accession, 0)
            ),
            "merged_repeat_bearing_proteins_count": merged_repeat_bearing_proteins_count,
            "merged_analyzed_protein_count": merged_analyzed_protein_count,
            "repeat_bearing_protein_percentage": accession_percentage,
        }

    for group in accession_groups:
        group.update(accession_metrics[group["accession"]])

    return {
        "accession_groups": accession_groups,
        "accession_groups_count": len(accession_groups),
        "source_genomes_count": source_genomes.count(),
        "source_runs_count": source_genomes.order_by().values("pipeline_run_id").distinct().count(),
        "source_repeat_calls_count": source_repeat_calls_count,
        "collapsed_repeat_calls_count": sum(collapsed_calls_by_accession.values()),
        "duplicate_source_repeat_calls_count": (
            included_residue_identity_count - sum(collapsed_calls_by_accession.values())
        ),
        "excluded_protein_identity_repeat_calls_count": (
            source_repeat_calls_count - included_protein_identity_count
        ),
        "excluded_residue_identity_repeat_calls_count": (
            source_repeat_calls_count - included_residue_identity_count
        ),
        "merged_repeat_bearing_proteins_count": sum(proteins_by_accession.values()),
        "conflict_accessions_count": len(accession_groups) - len(safe_accessions),
        "safe_accessions_count": len(safe_accessions),
        "analyzed_proteins_total": analyzed_proteins_total,
        "safe_repeat_bearing_proteins_count": safe_repeat_bearing_proteins_count,
        "repeat_bearing_protein_percentage": repeat_bearing_protein_percentage,
        "method_summary": method_summary,
        "residue_summary": residue_summary,
        "accession_metrics": accession_metrics,
    }


def _scoped_protein_occurrences(
    *,
    current_run=None,
    branch_taxon: Taxon | None = None,
    branch_taxa_ids=None,
    accessions=None,
):
    queryset = MergedProteinOccurrence.objects.all()
    resolved_branch_taxa_ids = _resolved_branch_taxa_ids(
        branch_taxon=branch_taxon,
        branch_taxa_ids=branch_taxa_ids,
    )
    if current_run is not None:
        queryset = queryset.filter(pipeline_run=current_run)
    if resolved_branch_taxa_ids is not None:
        queryset = queryset.filter(taxon_id__in=resolved_branch_taxa_ids)
    if accessions is not None:
        queryset = queryset.filter(summary__accession__in=accessions)
    return queryset


def _scoped_residue_occurrences(
    *,
    current_run=None,
    branch_taxon: Taxon | None = None,
    branch_taxa_ids=None,
    accessions=None,
):
    queryset = MergedResidueOccurrence.objects.all()
    resolved_branch_taxa_ids = _resolved_branch_taxa_ids(
        branch_taxon=branch_taxon,
        branch_taxa_ids=branch_taxa_ids,
    )
    if current_run is not None:
        queryset = queryset.filter(pipeline_run=current_run)
    if resolved_branch_taxa_ids is not None:
        queryset = queryset.filter(taxon_id__in=resolved_branch_taxa_ids)
    if accessions is not None:
        queryset = queryset.filter(summary__accession__in=accessions)
    return queryset


def _summary_counts_by_accession(occurrences_queryset):
    return {
        row["summary__accession"]: row["count"]
        for row in occurrences_queryset.values("summary__accession").annotate(
            count=Count("summary", distinct=True)
        )
    }


def _summary_counter(occurrences_queryset, *, field_name: str):
    return Counter(
        {
            row[field_name]: row["count"]
            for row in occurrences_queryset.values(field_name).annotate(
                count=Count("summary", distinct=True)
            )
        }
    )


def _raw_counts_by_accession(repeat_calls_queryset):
    return {
        row["genome__accession"]: row["count"]
        for row in repeat_calls_queryset.values("genome__accession").annotate(count=Count("pk"))
    }


def _trusted_protein_identity_repeat_calls(repeat_calls_queryset):
    return repeat_calls_queryset.annotate(
        trusted_protein_id=Trim("protein__protein_id"),
        trusted_method=Trim("method"),
    ).exclude(
        Q(trusted_protein_id="") | Q(trusted_protein_id__isnull=True) | Q(trusted_method="") | Q(trusted_method__isnull=True)
    )


def _trusted_residue_identity_repeat_calls(repeat_calls_queryset):
    return _trusted_protein_identity_repeat_calls(repeat_calls_queryset).annotate(
        trusted_residue=Trim("repeat_residue")
    ).exclude(Q(trusted_residue="") | Q(trusted_residue__isnull=True))
