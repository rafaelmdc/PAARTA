from importlib import import_module

from django.db.models import Q
from django.urls import reverse
from django.views.generic import DetailView

from ..merged import merged_repeat_call_groups
from ..models import PipelineRun, RepeatCall
from .filters import (
    _apply_branch_scope_filter,
    _resolve_browser_mode,
    _resolve_branch_scope,
    _resolve_current_run,
    _resolve_genome_filter,
    _resolve_protein_filter,
    _resolve_sequence_filter,
    _update_branch_scope_context,
)
from .formatting import _ordering_label, _parse_float, _parse_positive_int, _sort_dict_records
from .navigation import _url_with_query
from .pagination import VirtualScrollListView


def resolve_browser_facets(*, pipeline_run=None, pipeline_runs=None):
    return import_module(__package__).resolve_browser_facets(
        pipeline_run=pipeline_run,
        pipeline_runs=pipeline_runs,
    )


class RepeatCallListView(VirtualScrollListView):
    model = RepeatCall
    template_name = "browser/repeatcall_list.html"
    context_object_name = "repeat_calls"
    virtual_scroll_row_template_name = "browser/includes/repeatcall_list_rows.html"
    virtual_scroll_colspan = 10
    merged_ordering_map = {
        "accession": ("accession", "protein_name", "start", "end"),
        "-accession": ("-accession", "protein_name", "start", "end"),
        "protein_name": ("protein_name", "accession", "start", "end"),
        "-protein_name": ("-protein_name", "accession", "start", "end"),
        "gene_symbol": ("gene_symbol_label", "protein_name", "accession", "start"),
        "-gene_symbol": ("-gene_symbol_label", "protein_name", "accession", "start"),
        "method": ("method", "accession", "protein_name", "start"),
        "-method": ("-method", "accession", "protein_name", "start"),
        "coordinates": ("start", "end", "accession", "protein_name"),
        "-coordinates": ("-start", "-end", "accession", "protein_name"),
        "residue": ("repeat_residue", "accession", "protein_name", "start"),
        "-residue": ("-repeat_residue", "accession", "protein_name", "start"),
        "length": ("length", "accession", "protein_name", "start"),
        "-length": ("-length", "accession", "protein_name", "start"),
        "purity": ("normalized_purity", "accession", "protein_name", "start"),
        "-purity": ("-normalized_purity", "accession", "protein_name", "start"),
        "source_rows": ("source_count", "accession", "protein_name", "start"),
        "-source_rows": ("-source_count", "accession", "protein_name", "start"),
        "run": ("source_runs_count", "accession", "protein_name", "start"),
        "-run": ("-source_runs_count", "accession", "protein_name", "start"),
    }
    ordering_map = {
        "call_id": ("pipeline_run__run_id", "call_id"),
        "-call_id": ("pipeline_run__run_id", "-call_id"),
        "protein_name": ("pipeline_run__run_id", "protein_name", "accession", "start", "call_id"),
        "-protein_name": ("pipeline_run__run_id", "-protein_name", "accession", "start", "call_id"),
        "gene_symbol": ("pipeline_run__run_id", "gene_symbol", "accession", "protein_name", "start", "call_id"),
        "-gene_symbol": ("pipeline_run__run_id", "-gene_symbol", "accession", "protein_name", "start", "call_id"),
        "genome": ("pipeline_run__run_id", "accession", "protein_name", "start", "call_id"),
        "-genome": ("pipeline_run__run_id", "-accession", "protein_name", "start", "call_id"),
        "taxon": ("pipeline_run__run_id", "taxon__taxon_name", "accession", "protein_name", "start", "call_id"),
        "-taxon": ("pipeline_run__run_id", "-taxon__taxon_name", "accession", "protein_name", "start", "call_id"),
        "method": ("method", "pipeline_run__run_id", "accession", "protein_name", "start", "call_id"),
        "-method": ("-method", "pipeline_run__run_id", "accession", "protein_name", "start", "call_id"),
        "residue": ("repeat_residue", "pipeline_run__run_id", "accession", "protein_name", "start", "call_id"),
        "-residue": ("-repeat_residue", "pipeline_run__run_id", "accession", "protein_name", "start", "call_id"),
        "length": ("length", "pipeline_run__run_id", "accession", "protein_name", "start", "call_id"),
        "-length": ("-length", "pipeline_run__run_id", "accession", "protein_name", "start", "call_id"),
        "purity": ("purity", "pipeline_run__run_id", "accession", "protein_name", "start", "call_id"),
        "-purity": ("-purity", "pipeline_run__run_id", "accession", "protein_name", "start", "call_id"),
        "run": ("pipeline_run__run_id", "accession", "protein_name", "start", "call_id"),
        "-run": ("-pipeline_run__run_id", "accession", "protein_name", "start", "call_id"),
    }
    default_ordering = ("pipeline_run_id", "accession", "protein_name", "start", "id")

    def get_base_queryset(self):
        return (
            RepeatCall.objects.select_related("pipeline_run", "taxon")
            .defer(
                "aa_sequence",
                "codon_sequence",
            )
            .only(
                "id",
                "pipeline_run_id",
                "pipeline_run__id",
                "pipeline_run__run_id",
                "genome_id",
                "protein_id",
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
            )
        )

    def _load_filter_state(self):
        self.current_run = _resolve_current_run(self.request)
        self.branch_scope = _resolve_branch_scope(self.request)
        self.selected_branch_taxon = self.branch_scope["selected_branch_taxon"]
        self.current_accession = self.request.GET.get("accession", "").strip()
        self.current_method = self.request.GET.get("method", "").strip()
        self.current_residue = self.request.GET.get("residue", "").strip().upper()
        self.current_gene_symbol = self.request.GET.get("gene_symbol", "").strip()
        self.current_length_min = self.request.GET.get("length_min", "").strip()
        self.current_length_max = self.request.GET.get("length_max", "").strip()
        self.current_purity_min = self.request.GET.get("purity_min", "").strip()
        self.current_purity_max = self.request.GET.get("purity_max", "").strip()
        self.current_genome = self.request.GET.get("genome", "").strip()
        self.current_sequence = self.request.GET.get("sequence", "").strip()
        self.current_protein = self.request.GET.get("protein", "").strip()
        self.current_mode = _resolve_browser_mode(self.request)

    def use_cursor_pagination(self, queryset):
        return self.current_mode == "run" and hasattr(queryset, "filter") and self.uses_fast_default_ordering()

    def include_virtual_scroll_count(self, *, context=None, page_obj=None):
        return getattr(self, "current_mode", "run") != "run"

    def apply_search(self, queryset):
        query = self.get_search_query()
        if not query:
            return queryset

        return queryset.filter(
            Q(call_id__istartswith=query)
            | Q(accession__istartswith=query)
            | Q(protein_name__istartswith=query)
            | Q(gene_symbol__istartswith=query)
        )

    def apply_filters(self, queryset):
        self._load_filter_state()

        if self.current_run:
            queryset = queryset.filter(pipeline_run=self.current_run)

        queryset = _apply_branch_scope_filter(queryset, branch_scope=self.branch_scope, field_name="taxon_id")

        if self.current_accession:
            queryset = queryset.filter(accession__istartswith=self.current_accession)

        if self.current_genome:
            queryset = queryset.filter(genome__genome_id=self.current_genome)

        if self.current_sequence:
            queryset = queryset.filter(sequence__sequence_id=self.current_sequence)

        if self.current_protein:
            queryset = queryset.filter(protein__protein_id=self.current_protein)

        if self.current_method:
            queryset = queryset.filter(method=self.current_method)

        if self.current_residue:
            queryset = queryset.filter(repeat_residue=self.current_residue)

        if self.current_gene_symbol:
            queryset = queryset.filter(gene_symbol__istartswith=self.current_gene_symbol)

        length_min = _parse_positive_int(self.current_length_min)
        if length_min is not None:
            queryset = queryset.filter(length__gte=length_min)

        length_max = _parse_positive_int(self.current_length_max)
        if length_max is not None:
            queryset = queryset.filter(length__lte=length_max)

        purity_min = _parse_float(self.current_purity_min)
        if purity_min is not None:
            queryset = queryset.filter(purity__gte=purity_min)

        purity_max = _parse_float(self.current_purity_max)
        if purity_max is not None:
            queryset = queryset.filter(purity__lte=purity_max)

        return queryset

    def get_queryset(self):
        self._load_filter_state()
        if self.current_mode == "merged":
            records = merged_repeat_call_groups(
                current_run=self.current_run,
                branch_taxon=self.selected_branch_taxon,
                branch_taxa_ids=self.branch_scope["branch_taxa_ids"],
                search_query=self.get_search_query(),
                gene_symbol=self.current_gene_symbol,
                accession_query=self.current_accession,
                genome_id=self.current_genome,
                protein_id=self.current_protein,
                method=self.current_method,
                residue=self.current_residue,
                length_min=self.current_length_min,
                length_max=self.current_length_max,
                purity_min=self.current_purity_min,
                purity_max=self.current_purity_max,
            )
            return _sort_dict_records(
                records,
                requested_ordering=self.request.GET.get("order_by", "").strip(),
                default_ordering="call_id",
                key_map={
                    "call_id": lambda record: (
                        record["accession"],
                        record["protein_name"],
                        record["start"],
                        record["end"],
                        record["method"],
                    ),
                    "accession": lambda record: (
                        record["accession"],
                        record["protein_name"],
                        record["start"],
                        record["end"],
                    ),
                    "protein_name": lambda record: (
                        record["protein_name"],
                        record["accession"],
                        record["start"],
                        record["end"],
                    ),
                    "gene_symbol": lambda record: (
                        record["gene_symbol_label"],
                        record["protein_name"],
                        record["accession"],
                        record["start"],
                    ),
                    "coordinates": lambda record: (
                        record["start"],
                        record["end"],
                        record["accession"],
                        record["protein_name"],
                    ),
                    "method": lambda record: (
                        record["method"],
                        record["accession"],
                        record["protein_name"],
                        record["start"],
                    ),
                    "residue": lambda record: (
                        record["repeat_residue"],
                        record["accession"],
                        record["protein_name"],
                        record["start"],
                    ),
                    "length": lambda record: (
                        record["length"],
                        record["accession"],
                        record["protein_name"],
                        record["start"],
                    ),
                    "purity": lambda record: (
                        float(record["normalized_purity"]),
                        record["accession"],
                        record["protein_name"],
                        record["start"],
                    ),
                    "run": lambda record: (
                        record["source_runs_count"],
                        record["accession"],
                        record["protein_name"],
                        record["start"],
                    ),
                    "source_rows": lambda record: (
                        record["source_count"],
                        record["accession"],
                        record["protein_name"],
                        record["start"],
                    ),
                },
            )
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.is_virtual_scroll_fragment_request() and getattr(self, "current_mode", "run") == "run":
            return context
        current_run = getattr(self, "current_run", None)
        run_choices = PipelineRun.objects.order_by("-imported_at", "run_id")
        facet_choices = resolve_browser_facets(
            pipeline_run=current_run,
            pipeline_runs=run_choices,
        )

        context["current_run"] = current_run
        context["current_run_id"] = current_run.run_id if current_run else ""
        context["current_mode"] = getattr(self, "current_mode", "run")
        context["run_choices"] = run_choices
        _update_branch_scope_context(context, getattr(self, "branch_scope", _resolve_branch_scope(self.request)))
        context["current_accession"] = getattr(self, "current_accession", "")
        context["current_method"] = getattr(self, "current_method", "")
        context["current_residue"] = getattr(self, "current_residue", "")
        context["current_gene_symbol"] = getattr(self, "current_gene_symbol", "")
        context["current_length_min"] = getattr(self, "current_length_min", "")
        context["current_length_max"] = getattr(self, "current_length_max", "")
        context["current_purity_min"] = getattr(self, "current_purity_min", "")
        context["current_purity_max"] = getattr(self, "current_purity_max", "")
        context["current_genome"] = getattr(self, "current_genome", "")
        context["current_sequence"] = getattr(self, "current_sequence", "")
        context["current_protein"] = getattr(self, "current_protein", "")
        context["selected_genome"] = _resolve_genome_filter(current_run, context["current_genome"])
        context["selected_sequence"] = _resolve_sequence_filter(current_run, context["current_sequence"])
        context["selected_protein"] = _resolve_protein_filter(current_run, context["current_protein"])
        context["method_choices"] = facet_choices["methods"]
        context["residue_choices"] = facet_choices["residues"]
        if context["current_mode"] == "merged":
            context["sort_links"] = self.build_sort_links(
                self.merged_ordering_map,
                current_order_by=context["current_order_by"],
            )
            context["ordering_options"] = [
                {"value": value, "label": _ordering_label(value)}
                for value in self.merged_ordering_map.keys()
            ]
        return context


class RepeatCallDetailView(DetailView):
    model = RepeatCall
    template_name = "browser/repeatcall_detail.html"
    context_object_name = "repeat_call"

    def get_queryset(self):
        return RepeatCall.objects.select_related("pipeline_run", "genome", "sequence", "protein", "taxon")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        repeat_call = self.object
        context["taxon_detail_url"] = _url_with_query(
            reverse("browser:taxon-detail", args=[repeat_call.taxon.pk]),
            run=repeat_call.pipeline_run.run_id,
        )
        context["repeatcall_list_url"] = _url_with_query(
            reverse("browser:repeatcall-list"),
            run=repeat_call.pipeline_run.run_id,
            protein=repeat_call.protein.protein_id,
        )
        context["sequence_detail_url"] = reverse("browser:sequence-detail", args=[repeat_call.sequence.pk])
        context["run_detail_url"] = reverse("browser:run-detail", args=[repeat_call.pipeline_run.pk])
        return context
