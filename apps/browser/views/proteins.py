from importlib import import_module

from django.db.models import Count, Exists, Max, Min, OuterRef, Q
from django.urls import reverse
from django.views.generic import DetailView

from ..merged import materialize_merged_protein_groups, merged_protein_group_queryset
from ..models import PipelineRun, Protein, RepeatCall
from .filters import (
    _apply_branch_scope_filter,
    _repeat_call_filter_q,
    _resolve_browser_mode,
    _resolve_branch_scope,
    _resolve_current_run,
    _resolve_genome_filter,
    _resolve_sequence_filter,
    _update_branch_scope_context,
)
from .formatting import _ordering_label, _sort_dict_records
from .navigation import _url_with_query
from .pagination import VirtualScrollListView
from .querysets import _annotated_proteins


def resolve_browser_facets(*, pipeline_run=None, pipeline_runs=None):
    return import_module(__package__).resolve_browser_facets(
        pipeline_run=pipeline_run,
        pipeline_runs=pipeline_runs,
    )


class ProteinListView(VirtualScrollListView):
    model = Protein
    template_name = "browser/protein_list.html"
    context_object_name = "proteins"
    virtual_scroll_row_template_name = "browser/includes/protein_list_rows.html"
    virtual_scroll_colspan = 6
    merged_ordering_map = {
        "protein_name": ("protein_name", "accession"),
        "-protein_name": ("-protein_name", "accession"),
        "gene_symbol": ("gene_symbol", "protein_name", "accession"),
        "-gene_symbol": ("-gene_symbol", "protein_name", "accession"),
        "accession": ("accession", "protein_name"),
        "-accession": ("-accession", "protein_name"),
        "run": ("scoped_source_runs_count", "protein_name", "accession"),
        "-run": ("-scoped_source_runs_count", "protein_name", "accession"),
        "source_proteins": ("scoped_source_proteins_count", "protein_name", "accession"),
        "-source_proteins": ("-scoped_source_proteins_count", "protein_name", "accession"),
        "calls": ("scoped_collapsed_repeat_calls_count", "protein_name", "accession"),
        "-calls": ("-scoped_collapsed_repeat_calls_count", "protein_name", "accession"),
    }
    merged_default_ordering = ("protein_name", "accession")
    ordering_map = {
        "protein_name": ("pipeline_run__run_id", "accession", "protein_name", "protein_id"),
        "-protein_name": ("pipeline_run__run_id", "accession", "-protein_name", "protein_id"),
        "gene_symbol": ("pipeline_run__run_id", "gene_symbol", "accession", "protein_name", "protein_id"),
        "-gene_symbol": ("pipeline_run__run_id", "-gene_symbol", "accession", "protein_name", "protein_id"),
        "protein_length": ("pipeline_run__run_id", "protein_length", "accession", "protein_name", "protein_id"),
        "-protein_length": ("pipeline_run__run_id", "-protein_length", "accession", "protein_name", "protein_id"),
        "accession": ("pipeline_run__run_id", "accession", "protein_name", "protein_id"),
        "-accession": ("pipeline_run__run_id", "-accession", "protein_name", "protein_id"),
        "taxon": ("taxon__taxon_name", "pipeline_run__run_id", "accession", "protein_name", "protein_id"),
        "-taxon": ("-taxon__taxon_name", "pipeline_run__run_id", "accession", "protein_name", "protein_id"),
        "run": ("pipeline_run__run_id", "accession", "protein_name", "protein_id"),
        "-run": ("-pipeline_run__run_id", "accession", "protein_name", "protein_id"),
        "calls": ("-repeat_calls_count", "pipeline_run__run_id", "accession", "protein_name", "protein_id"),
        "-calls": ("repeat_calls_count", "pipeline_run__run_id", "accession", "protein_name", "protein_id"),
    }
    default_ordering = ("pipeline_run_id", "accession", "protein_name", "id")

    def get_base_queryset(self):
        return _annotated_proteins(
            Protein.objects.select_related("pipeline_run", "taxon")
            .defer("amino_acid_sequence")
            .only(
                "id",
                "pipeline_run_id",
                "pipeline_run__id",
                "pipeline_run__run_id",
                "genome_id",
                "taxon_id",
                "taxon__id",
                "taxon__taxon_name",
                "protein_id",
                "protein_name",
                "protein_length",
                "accession",
                "gene_symbol",
            )
        )

    def _load_filter_state(self):
        self.current_run = _resolve_current_run(self.request)
        self.branch_scope = _resolve_branch_scope(self.request)
        self.selected_branch_taxon = self.branch_scope["selected_branch_taxon"]
        self.current_accession = self.request.GET.get("accession", "").strip()
        self.current_gene_symbol = self.request.GET.get("gene_symbol", "").strip()
        self.current_method = self.request.GET.get("method", "").strip()
        self.current_residue = self.request.GET.get("residue", "").strip().upper()
        self.current_length_min = self.request.GET.get("length_min", "").strip()
        self.current_length_max = self.request.GET.get("length_max", "").strip()
        self.current_purity_min = self.request.GET.get("purity_min", "").strip()
        self.current_purity_max = self.request.GET.get("purity_max", "").strip()
        self.current_genome = self.request.GET.get("genome", "").strip()
        self.current_sequence = self.request.GET.get("sequence", "").strip()
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
            Q(protein_id__istartswith=query)
            | Q(protein_name__istartswith=query)
            | Q(gene_symbol__istartswith=query)
            | Q(accession__istartswith=query)
        )

    def apply_filters(self, queryset):
        self._load_filter_state()

        if self.current_run:
            queryset = queryset.filter(pipeline_run=self.current_run)

        queryset = _apply_branch_scope_filter(queryset, branch_scope=self.branch_scope, field_name="taxon_id")

        if self.current_accession:
            queryset = queryset.filter(accession__istartswith=self.current_accession)

        if self.current_gene_symbol:
            queryset = queryset.filter(gene_symbol__istartswith=self.current_gene_symbol)

        if self.current_genome:
            queryset = queryset.filter(genome__genome_id=self.current_genome)

        if self.current_sequence:
            queryset = queryset.filter(sequence__sequence_id=self.current_sequence)

        call_filters = _repeat_call_filter_q(
            method=self.current_method,
            residue=self.current_residue,
            length_min=self.current_length_min,
            length_max=self.current_length_max,
            purity_min=self.current_purity_min,
            purity_max=self.current_purity_max,
        )
        if call_filters is not None:
            matching_calls = RepeatCall.objects.filter(protein=OuterRef("pk")).filter(call_filters)
            queryset = queryset.annotate(has_matching_call=Exists(matching_calls)).filter(has_matching_call=True)

        return queryset

    def get_queryset(self):
        self._load_filter_state()
        if self.current_mode == "merged":
            queryset = merged_protein_group_queryset(
                current_run=self.current_run,
                branch_taxon=self.selected_branch_taxon,
                branch_taxa_ids=self.branch_scope["branch_taxa_ids"],
                search_query=self.get_search_query(),
                gene_symbol=self.current_gene_symbol,
                accession_query=self.current_accession,
                genome_id=self.current_genome,
                protein_id="",
                method=self.current_method,
                residue=self.current_residue,
                length_min=self.current_length_min,
                length_max=self.current_length_max,
                purity_min=self.current_purity_min,
                purity_max=self.current_purity_max,
            )
            requested_ordering = self.request.GET.get("order_by", "").strip()
            ordering = self.merged_ordering_map.get(requested_ordering, self.merged_default_ordering)
            return queryset.order_by(*ordering, "id")
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.is_virtual_scroll_fragment_request() and getattr(self, "current_mode", "run") == "run":
            return context
        if getattr(self, "current_mode", "run") == "merged":
            page_obj = context.get("page_obj")
            page_summaries = list(getattr(page_obj, "object_list", []))
            merged_groups = materialize_merged_protein_groups(
                page_summaries,
                current_run=getattr(self, "current_run", None),
                branch_taxon=getattr(self, "selected_branch_taxon", None),
                branch_taxa_ids=getattr(self, "branch_scope", {}).get("branch_taxa_ids"),
                search_query=self.get_search_query(),
                gene_symbol=getattr(self, "current_gene_symbol", ""),
                accession_query=getattr(self, "current_accession", ""),
                genome_id=getattr(self, "current_genome", ""),
                protein_id="",
                method=getattr(self, "current_method", ""),
                residue=getattr(self, "current_residue", ""),
                length_min=getattr(self, "current_length_min", ""),
                length_max=getattr(self, "current_length_max", ""),
                purity_min=getattr(self, "current_purity_min", ""),
                purity_max=getattr(self, "current_purity_max", ""),
                provenance_preview_limit=2,
            )
            if page_obj is not None:
                page_obj.object_list = merged_groups
            context["object_list"] = merged_groups
            context[self.context_object_name] = merged_groups
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
        context["current_gene_symbol"] = getattr(self, "current_gene_symbol", "")
        context["current_method"] = getattr(self, "current_method", "")
        context["current_residue"] = getattr(self, "current_residue", "")
        context["current_length_min"] = getattr(self, "current_length_min", "")
        context["current_length_max"] = getattr(self, "current_length_max", "")
        context["current_purity_min"] = getattr(self, "current_purity_min", "")
        context["current_purity_max"] = getattr(self, "current_purity_max", "")
        context["current_genome"] = getattr(self, "current_genome", "")
        context["current_sequence"] = getattr(self, "current_sequence", "")
        context["selected_genome"] = _resolve_genome_filter(current_run, context["current_genome"])
        context["selected_sequence"] = _resolve_sequence_filter(current_run, context["current_sequence"])
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


class ProteinDetailView(DetailView):
    model = Protein
    template_name = "browser/protein_detail.html"
    context_object_name = "protein"

    def get_queryset(self):
        return Protein.objects.select_related("pipeline_run", "genome", "sequence", "taxon")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        protein = self.object
        repeat_calls = protein.repeat_calls.select_related("taxon").order_by("method", "repeat_residue", "start", "call_id")

        context["repeat_calls_count"] = repeat_calls.count()
        context["call_summaries"] = (
            repeat_calls.values("method", "repeat_residue")
            .annotate(
                total=Count("pk"),
                min_length=Min("length"),
                max_length=Max("length"),
            )
            .order_by("method", "repeat_residue")
        )
        context["repeat_call_preview"] = repeat_calls[:12]
        context["taxon_detail_url"] = _url_with_query(
            reverse("browser:taxon-detail", args=[protein.taxon.pk]),
            run=protein.pipeline_run.run_id,
        )
        context["repeatcall_browser_url"] = _url_with_query(
            reverse("browser:repeatcall-list"),
            run=protein.pipeline_run.run_id,
            protein=protein.protein_id,
        )
        context["sequence_detail_url"] = reverse("browser:sequence-detail", args=[protein.sequence.pk])
        context["protein_list_url"] = _url_with_query(
            reverse("browser:protein-list"),
            run=protein.pipeline_run.run_id,
            genome=protein.genome.genome_id,
        )
        context["run_detail_url"] = reverse("browser:run-detail", args=[protein.pipeline_run.pk])
        return context
