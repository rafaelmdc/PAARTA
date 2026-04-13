from django.db.models import Count, Exists, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce

from ..models import MergedResidueOccurrence, MergedResidueSummary, RepeatCall, Taxon, TaxonClosure
from .identity import (
    _identity_merged_residue_groups_from_repeat_calls,
    _protein_residue_identity_key,
    _trim_group_provenance,
)
from .metrics import _parse_float, _parse_positive_int


def merged_repeat_call_groups(
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
        merged_repeat_call_group_queryset(
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
    return materialize_merged_repeat_call_groups(
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


def count_merged_repeat_call_groups(
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
    return queryset.values("summary_id").distinct().count()


def merged_repeat_call_group_queryset(
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
    queryset = MergedResidueSummary.objects.all()
    queryset = _apply_residue_summary_filters(
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
    return _annotate_residue_sort_counts(
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


def materialize_merged_repeat_call_groups(
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
        (summary.accession, summary.protein_id, summary.method, summary.repeat_residue)
        for summary in summaries
    ]
    if not summary_keys:
        return []

    source_repeat_calls = _residue_source_repeat_calls_for_keys(
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
        (group["accession"], group["protein_id"], group["method"], group["repeat_residue"]): group
        for group in _identity_merged_residue_groups_from_repeat_calls(source_repeat_calls)
    }
    return [
        _trim_group_provenance(groups_by_key[key], limit=provenance_preview_limit)
        for key in summary_keys
        if key in groups_by_key
    ]


def source_repeat_call_queryset(
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
    queryset = _merged_repeat_call_queryset().exclude(accession="")

    if current_run is not None:
        queryset = queryset.filter(pipeline_run=current_run)

    resolved_branch_taxa_ids = _resolved_branch_taxa_ids(
        branch_taxon=branch_taxon,
        branch_taxa_ids=branch_taxa_ids,
    )
    if resolved_branch_taxa_ids is not None:
        queryset = queryset.filter(taxon_id__in=resolved_branch_taxa_ids)

    if search_query:
        queryset = queryset.filter(
            Q(call_id__icontains=search_query)
            | Q(protein_name__icontains=search_query)
            | Q(protein__protein_id__icontains=search_query)
            | Q(gene_symbol__icontains=search_query)
            | Q(accession__icontains=search_query)
        )

    if gene_symbol:
        queryset = queryset.filter(
            Q(gene_symbol__icontains=gene_symbol) | Q(sequence__gene_symbol__icontains=gene_symbol)
        )

    if accession_query:
        queryset = queryset.filter(accession__icontains=accession_query)

    if genome_id:
        queryset = queryset.filter(genome__genome_id=genome_id)

    if protein_id:
        queryset = queryset.filter(protein__protein_id=protein_id)

    if method:
        queryset = queryset.filter(method=method)

    if residue:
        queryset = queryset.filter(repeat_residue=residue)

    parsed_length_min = _parse_positive_int(length_min)
    if parsed_length_min is not None:
        queryset = queryset.filter(length__gte=parsed_length_min)

    parsed_length_max = _parse_positive_int(length_max)
    if parsed_length_max is not None:
        queryset = queryset.filter(length__lte=parsed_length_max)

    parsed_purity_min = _parse_float(purity_min)
    if parsed_purity_min is not None:
        queryset = queryset.filter(purity__gte=parsed_purity_min)

    parsed_purity_max = _parse_float(purity_max)
    if parsed_purity_max is not None:
        queryset = queryset.filter(purity__lte=parsed_purity_max)

    return queryset.order_by("accession", "protein_name", "method", "start", "call_id")


def _apply_residue_summary_filters(
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

    if genome_id or length_min or length_max or purity_min or purity_max:
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

    return queryset


def _annotate_residue_sort_counts(
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
    matching_calls = _residue_matching_repeat_calls(
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
    return queryset.annotate(
        scoped_source_runs_count=Coalesce(
            _count_subquery(matching_calls, count_field="pipeline_run", distinct=True),
            Value(0),
        ),
        scoped_source_count=Coalesce(
            _count_subquery(matching_calls, count_field="pk"),
            Value(0),
        ),
    )


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


def _residue_source_repeat_calls_for_keys(
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
    residues = {key[3] for key in summary_key_set}
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
            repeat_residue__in=residues,
        )
        if _protein_residue_identity_key(repeat_call) in summary_key_set
    ]


def _merged_repeat_call_queryset():
    return (
        RepeatCall.objects.select_related("pipeline_run", "genome", "protein", "taxon")
        .defer(
            "codon_sequence",
            "codon_metric_name",
            "codon_metric_value",
            "window_definition",
            "template_name",
            "merge_rule",
            "score",
            "protein__amino_acid_sequence",
        )
        .only(
            "id",
            "pipeline_run_id",
            "pipeline_run__id",
            "pipeline_run__run_id",
            "pipeline_run__imported_at",
            "genome_id",
            "genome__id",
            "genome__accession",
            "genome__genome_id",
            "protein_id",
            "protein__id",
            "protein__protein_id",
            "protein__protein_name",
            "protein__protein_length",
            "protein__gene_symbol",
            "taxon_id",
            "taxon__id",
            "taxon__taxon_name",
            "call_id",
            "method",
            "accession",
            "gene_symbol",
            "protein_name",
            "protein_length",
            "start",
            "end",
            "length",
            "repeat_residue",
            "purity",
            "aa_sequence",
        )
    )


def _resolved_branch_taxa_ids(*, branch_taxon: Taxon | None = None, branch_taxa_ids=None):
    if branch_taxa_ids is not None:
        return branch_taxa_ids
    if branch_taxon is not None:
        return _branch_taxon_ids(branch_taxon)
    return None


def _branch_taxon_ids(taxon: Taxon):
    return TaxonClosure.objects.filter(ancestor=taxon).order_by().values_list("descendant_id", flat=True)


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


def _count_subquery(queryset, *, count_field: str, distinct: bool = False):
    return Subquery(
        queryset.annotate(_group=Value(1))
        .values("_group")
        .annotate(total=Count(count_field, distinct=distinct))
        .values("total")[:1],
        output_field=IntegerField(),
    )
