from django.db.models import CharField, Count, Exists, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Cast, Coalesce, Concat

from ..models import (
    MergedProteinOccurrence,
    MergedProteinSummary,
    MergedResidueOccurrence,
    MergedResidueSummary,
    Taxon,
)
from .identity import (
    _identity_merged_protein_groups_from_repeat_calls,
    _protein_identity_key,
    _trim_group_provenance,
)
from .repeat_calls import _resolved_branch_taxa_ids, source_repeat_call_queryset


def merged_protein_groups(
    *,
    current_run=None,
    branch_taxon: Taxon | None = None,
    branch_taxa_ids=None,
    search_query: str = "",
    gene_symbol: str = "",
    accession_query: str = "",
    genome_id: str = "",
    protein_id: str = "",
    method: str = "",
    residue: str = "",
    length_min: str = "",
    length_max: str = "",
    purity_min: str = "",
    purity_max: str = "",
    provenance_preview_limit: int | None = None,
):
    summaries = list(
        merged_protein_group_queryset(
            current_run=current_run,
            branch_taxon=branch_taxon,
            branch_taxa_ids=branch_taxa_ids,
            search_query=search_query,
            gene_symbol=gene_symbol,
            accession_query=accession_query,
            genome_id=genome_id,
            protein_id=protein_id,
            method=method,
            residue=residue,
            length_min=length_min,
            length_max=length_max,
            purity_min=purity_min,
            purity_max=purity_max,
        )
    )
    return materialize_merged_protein_groups(
        summaries,
        current_run=current_run,
        branch_taxon=branch_taxon,
        branch_taxa_ids=branch_taxa_ids,
        search_query=search_query,
        gene_symbol=gene_symbol,
        accession_query=accession_query,
        genome_id=genome_id,
        protein_id=protein_id,
        method=method,
        residue=residue,
        length_min=length_min,
        length_max=length_max,
        purity_min=purity_min,
        purity_max=purity_max,
        provenance_preview_limit=provenance_preview_limit,
    )


def count_merged_protein_groups(
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
    return queryset.values("summary_id").distinct().count()


def merged_protein_group_queryset(
    *,
    current_run=None,
    branch_taxon: Taxon | None = None,
    branch_taxa_ids=None,
    search_query: str = "",
    gene_symbol: str = "",
    accession_query: str = "",
    genome_id: str = "",
    protein_id: str = "",
    method: str = "",
    residue: str = "",
    length_min: str = "",
    length_max: str = "",
    purity_min: str = "",
    purity_max: str = "",
):
    queryset = MergedProteinSummary.objects.all()
    queryset = _apply_protein_summary_filters(
        queryset,
        current_run=current_run,
        branch_taxon=branch_taxon,
        branch_taxa_ids=branch_taxa_ids,
        search_query=search_query,
        gene_symbol=gene_symbol,
        accession_query=accession_query,
        genome_id=genome_id,
        protein_id=protein_id,
        method=method,
        residue=residue,
        length_min=length_min,
        length_max=length_max,
        purity_min=purity_min,
        purity_max=purity_max,
    )
    return _annotate_protein_sort_counts(
        queryset,
        current_run=current_run,
        branch_taxon=branch_taxon,
        branch_taxa_ids=branch_taxa_ids,
        search_query=search_query,
        gene_symbol=gene_symbol,
        accession_query=accession_query,
        genome_id=genome_id,
        protein_id=protein_id,
        method=method,
        residue=residue,
        length_min=length_min,
        length_max=length_max,
        purity_min=purity_min,
        purity_max=purity_max,
    )


def materialize_merged_protein_groups(
    summaries,
    *,
    current_run=None,
    branch_taxon: Taxon | None = None,
    branch_taxa_ids=None,
    search_query: str = "",
    gene_symbol: str = "",
    accession_query: str = "",
    genome_id: str = "",
    protein_id: str = "",
    method: str = "",
    residue: str = "",
    length_min: str = "",
    length_max: str = "",
    purity_min: str = "",
    purity_max: str = "",
    provenance_preview_limit: int | None = None,
):
    summary_keys = [
        (summary.accession, summary.protein_id, summary.method)
        for summary in summaries
    ]
    if not summary_keys:
        return []

    source_repeat_calls = _protein_source_repeat_calls_for_keys(
        summary_keys,
        current_run=current_run,
        branch_taxon=branch_taxon,
        branch_taxa_ids=branch_taxa_ids,
        search_query=search_query,
        gene_symbol=gene_symbol,
        accession_query=accession_query,
        genome_id=genome_id,
        protein_id=protein_id,
        method=method,
        residue=residue,
        length_min=length_min,
        length_max=length_max,
        purity_min=purity_min,
        purity_max=purity_max,
    )
    groups_by_key = {
        (group["accession"], group["protein_id"], group["method"]): group
        for group in _identity_merged_protein_groups_from_repeat_calls(source_repeat_calls)
    }
    return [
        _trim_group_provenance(groups_by_key[key], limit=provenance_preview_limit)
        for key in summary_keys
        if key in groups_by_key
    ]


def _apply_protein_summary_filters(
    queryset,
    *,
    current_run=None,
    branch_taxon: Taxon | None = None,
    branch_taxa_ids=None,
    search_query: str = "",
    gene_symbol: str = "",
    accession_query: str = "",
    genome_id: str = "",
    protein_id: str = "",
    method: str = "",
    residue: str = "",
    length_min: str = "",
    length_max: str = "",
    purity_min: str = "",
    purity_max: str = "",
):
    occurrence_exists = _protein_occurrence_exists(
        current_run=current_run,
        branch_taxon=branch_taxon,
        branch_taxa_ids=branch_taxa_ids,
    )
    if occurrence_exists is not None:
        queryset = queryset.filter(Exists(occurrence_exists))

    if search_query:
        queryset = queryset.filter(
            Q(protein_id__icontains=search_query)
            | Q(protein_name__icontains=search_query)
            | Q(gene_symbol_label__icontains=search_query)
            | Q(accession__icontains=search_query)
        )

    if gene_symbol:
        queryset = queryset.filter(gene_symbol_label__icontains=gene_symbol)

    if accession_query:
        queryset = queryset.filter(accession__icontains=accession_query)

    if protein_id:
        queryset = queryset.filter(protein_id=protein_id)

    if method:
        queryset = queryset.filter(method=method)

    if residue:
        residue_occurrences = _residue_occurrence_exists(
            current_run=current_run,
            branch_taxon=branch_taxon,
            branch_taxa_ids=branch_taxa_ids,
        )
        residue_summaries = MergedResidueSummary.objects.filter(
            accession=OuterRef("accession"),
            protein_id=OuterRef("protein_id"),
            method=OuterRef("method"),
            repeat_residue=residue,
        )
        if residue_occurrences is not None:
            residue_summaries = residue_summaries.filter(Exists(residue_occurrences))
        queryset = queryset.filter(Exists(residue_summaries))

    if genome_id or length_min or length_max or purity_min or purity_max:
        queryset = queryset.filter(
            Exists(
                _protein_matching_repeat_calls(
                    current_run=current_run,
                    branch_taxon=branch_taxon,
                    branch_taxa_ids=branch_taxa_ids,
                    search_query=search_query,
                    gene_symbol=gene_symbol,
                    accession_query=accession_query,
                    genome_id=genome_id,
                    protein_id=protein_id,
                    method=method,
                    residue=residue,
                    length_min=length_min,
                    length_max=length_max,
                    purity_min=purity_min,
                    purity_max=purity_max,
                )
            )
        )

    return queryset


def _annotate_protein_sort_counts(
    queryset,
    *,
    current_run=None,
    branch_taxon: Taxon | None = None,
    branch_taxa_ids=None,
    search_query: str = "",
    gene_symbol: str = "",
    accession_query: str = "",
    genome_id: str = "",
    protein_id: str = "",
    method: str = "",
    residue: str = "",
    length_min: str = "",
    length_max: str = "",
    purity_min: str = "",
    purity_max: str = "",
):
    matching_calls = _protein_matching_repeat_calls(
        current_run=current_run,
        branch_taxon=branch_taxon,
        branch_taxa_ids=branch_taxa_ids,
        search_query=search_query,
        gene_symbol=gene_symbol,
        accession_query=accession_query,
        genome_id=genome_id,
        protein_id=protein_id,
        method=method,
        residue=residue,
        length_min=length_min,
        length_max=length_max,
        purity_min=purity_min,
        purity_max=purity_max,
    )
    residue_summaries = _protein_matching_residue_summaries(
        current_run=current_run,
        branch_taxon=branch_taxon,
        branch_taxa_ids=branch_taxa_ids,
        search_query=search_query,
        gene_symbol=gene_symbol,
        accession_query=accession_query,
        genome_id=genome_id,
        protein_id=protein_id,
        method=method,
        residue=residue,
        length_min=length_min,
        length_max=length_max,
        purity_min=purity_min,
        purity_max=purity_max,
    )
    collapsed_keys = matching_calls.annotate(
        collapsed_key=Concat(
            Cast("start", CharField()),
            Value("|"),
            Cast("end", CharField()),
            Value("|"),
            "repeat_residue",
            Value("|"),
            Cast("length", CharField()),
            Value("|"),
            Cast("purity", CharField()),
        )
    )
    return queryset.annotate(
        scoped_source_runs_count=Coalesce(
            _count_subquery(matching_calls, count_field="pipeline_run", distinct=True),
            Value(0),
        ),
        scoped_source_proteins_count=Coalesce(
            _count_subquery(matching_calls, count_field="protein", distinct=True),
            Value(0),
        ),
        scoped_collapsed_repeat_calls_count=Coalesce(
            _count_subquery(collapsed_keys, count_field="collapsed_key", distinct=True),
            Value(0),
        ),
        scoped_residue_groups_count=Coalesce(
            _count_subquery(residue_summaries, count_field="pk", distinct=True),
            Value(0),
        ),
    )


def _protein_matching_repeat_calls(
    *,
    current_run=None,
    branch_taxon: Taxon | None = None,
    branch_taxa_ids=None,
    search_query: str = "",
    gene_symbol: str = "",
    accession_query: str = "",
    genome_id: str = "",
    protein_id: str = "",
    method: str = "",
    residue: str = "",
    length_min: str = "",
    length_max: str = "",
    purity_min: str = "",
    purity_max: str = "",
):
    return (
        source_repeat_call_queryset(
            current_run=current_run,
            branch_taxon=branch_taxon,
            branch_taxa_ids=branch_taxa_ids,
            search_query=search_query,
            gene_symbol=gene_symbol,
            accession_query=accession_query,
            genome_id=genome_id,
            protein_id=protein_id,
            method=method,
            residue=residue,
            length_min=length_min,
            length_max=length_max,
            purity_min=purity_min,
            purity_max=purity_max,
        )
        .order_by()
        .filter(
            accession=OuterRef("accession"),
            protein__protein_id=OuterRef("protein_id"),
            method=OuterRef("method"),
        )
    )


def _protein_matching_residue_summaries(
    *,
    current_run=None,
    branch_taxon: Taxon | None = None,
    branch_taxa_ids=None,
    search_query: str = "",
    gene_symbol: str = "",
    accession_query: str = "",
    genome_id: str = "",
    protein_id: str = "",
    method: str = "",
    residue: str = "",
    length_min: str = "",
    length_max: str = "",
    purity_min: str = "",
    purity_max: str = "",
):
    queryset = MergedResidueSummary.objects.filter(
        accession=OuterRef("accession"),
        protein_id=OuterRef("protein_id"),
        method=OuterRef("method"),
    )
    occurrence_exists = _residue_occurrence_exists(
        current_run=current_run,
        branch_taxon=branch_taxon,
        branch_taxa_ids=branch_taxa_ids,
    )
    if occurrence_exists is not None:
        queryset = queryset.filter(Exists(occurrence_exists))
    if search_query:
        queryset = queryset.filter(
            Q(protein_id__icontains=search_query)
            | Q(protein_name__icontains=search_query)
            | Q(gene_symbol_label__icontains=search_query)
            | Q(accession__icontains=search_query)
        )
    if gene_symbol:
        queryset = queryset.filter(gene_symbol_label__icontains=gene_symbol)
    if accession_query:
        queryset = queryset.filter(accession__icontains=accession_query)
    if protein_id:
        queryset = queryset.filter(protein_id=protein_id)
    if method:
        queryset = queryset.filter(method=method)
    if residue:
        queryset = queryset.filter(repeat_residue=residue)
    queryset = queryset.filter(
        Exists(
            _residue_matching_repeat_calls(
                current_run=current_run,
                branch_taxon=branch_taxon,
                branch_taxa_ids=branch_taxa_ids,
                search_query=search_query,
                gene_symbol=gene_symbol,
                accession_query=accession_query,
                genome_id=genome_id,
                protein_id=protein_id,
                method=method,
                residue=residue,
                length_min=length_min,
                length_max=length_max,
                purity_min=purity_min,
                purity_max=purity_max,
            )
        )
    )
    return queryset.order_by()


def _protein_source_repeat_calls_for_keys(
    summary_keys,
    *,
    current_run=None,
    branch_taxon: Taxon | None = None,
    branch_taxa_ids=None,
    search_query: str = "",
    gene_symbol: str = "",
    accession_query: str = "",
    genome_id: str = "",
    protein_id: str = "",
    method: str = "",
    residue: str = "",
    length_min: str = "",
    length_max: str = "",
    purity_min: str = "",
    purity_max: str = "",
):
    if not summary_keys:
        return []

    summary_key_set = set(summary_keys)
    accessions = {key[0] for key in summary_key_set}
    protein_ids = {key[1] for key in summary_key_set}
    methods = {key[2] for key in summary_key_set}
    return [
        repeat_call
        for repeat_call in source_repeat_call_queryset(
            current_run=current_run,
            branch_taxon=branch_taxon,
            branch_taxa_ids=branch_taxa_ids,
            search_query=search_query,
            gene_symbol=gene_symbol,
            accession_query=accession_query,
            genome_id=genome_id,
            protein_id=protein_id,
            method=method,
            residue=residue,
            length_min=length_min,
            length_max=length_max,
            purity_min=purity_min,
            purity_max=purity_max,
        ).filter(
            accession__in=accessions,
            protein__protein_id__in=protein_ids,
            method__in=methods,
        )
        if _protein_identity_key(repeat_call) in summary_key_set
    ]


def _protein_occurrence_exists(*, current_run=None, branch_taxon: Taxon | None = None, branch_taxa_ids=None):
    queryset = MergedProteinOccurrence.objects.filter(summary_id=OuterRef("pk"))
    resolved_branch_taxa_ids = branch_taxa_ids
    if current_run is None and branch_taxon is None and resolved_branch_taxa_ids is None:
        return None
    if current_run is not None:
        queryset = queryset.filter(pipeline_run=current_run)
    resolved_branch_taxa_ids = _resolved_branch_taxa_ids(
        branch_taxon=branch_taxon,
        branch_taxa_ids=resolved_branch_taxa_ids,
    )
    if resolved_branch_taxa_ids is not None:
        queryset = queryset.filter(taxon_id__in=resolved_branch_taxa_ids)
    return queryset.order_by()


def _residue_occurrence_exists(*, current_run=None, branch_taxon: Taxon | None = None, branch_taxa_ids=None):
    resolved_branch_taxa_ids = _resolved_branch_taxa_ids(
        branch_taxon=branch_taxon,
        branch_taxa_ids=branch_taxa_ids,
    )
    if current_run is None and resolved_branch_taxa_ids is None:
        return None

    queryset = MergedResidueOccurrence.objects.filter(summary_id=OuterRef("pk"))
    if current_run is not None:
        queryset = queryset.filter(pipeline_run=current_run)
    if resolved_branch_taxa_ids is not None:
        queryset = queryset.filter(taxon_id__in=resolved_branch_taxa_ids)
    return queryset.order_by()


def _residue_matching_repeat_calls(
    *,
    current_run=None,
    branch_taxon: Taxon | None = None,
    branch_taxa_ids=None,
    search_query: str = "",
    gene_symbol: str = "",
    accession_query: str = "",
    genome_id: str = "",
    protein_id: str = "",
    method: str = "",
    residue: str = "",
    length_min: str = "",
    length_max: str = "",
    purity_min: str = "",
    purity_max: str = "",
):
    return (
        source_repeat_call_queryset(
            current_run=current_run,
            branch_taxon=branch_taxon,
            branch_taxa_ids=branch_taxa_ids,
            search_query=search_query,
            gene_symbol=gene_symbol,
            accession_query=accession_query,
            genome_id=genome_id,
            protein_id=protein_id,
            method=method,
            residue=residue,
            length_min=length_min,
            length_max=length_max,
            purity_min=purity_min,
            purity_max=purity_max,
        )
        .order_by()
        .filter(
            accession=OuterRef("accession"),
            protein__protein_id=OuterRef("protein_id"),
            method=OuterRef("method"),
            repeat_residue=OuterRef("repeat_residue"),
        )
    )
def _count_subquery(queryset, *, count_field: str, distinct: bool = False):
    return Subquery(
        queryset.annotate(_group=Value(1))
        .values("_group")
        .annotate(total=Count(count_field, distinct=distinct))
        .values("total")[:1],
        output_field=IntegerField(),
    )
