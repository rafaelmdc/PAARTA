from django.db.models import Q
from django.urls import reverse
from django.views.generic import DetailView

from ..models import PipelineRun, Sequence
from .filters import (
    _apply_branch_scope_filter,
    _resolve_branch_scope,
    _resolve_current_run,
    _resolve_genome_filter,
    _update_branch_scope_context,
)
from .navigation import _url_with_query
from .pagination import VirtualScrollListView
from .querysets import _annotated_sequences


class SequenceListView(VirtualScrollListView):
    model = Sequence
    template_name = "browser/sequence_list.html"
    context_object_name = "sequences"
    virtual_scroll_row_template_name = "browser/includes/sequence_list_rows.html"
    virtual_scroll_colspan = 7
    ordering_map = {
        "sequence_name": ("pipeline_run__run_id", "sequence_name", "sequence_id"),
        "-sequence_name": ("pipeline_run__run_id", "-sequence_name", "sequence_id"),
        "gene_symbol": ("pipeline_run__run_id", "gene_symbol", "sequence_name", "sequence_id"),
        "-gene_symbol": ("pipeline_run__run_id", "-gene_symbol", "sequence_name", "sequence_id"),
        "genome": ("genome__accession", "pipeline_run__run_id", "sequence_name", "sequence_id"),
        "-genome": ("-genome__accession", "pipeline_run__run_id", "sequence_name", "sequence_id"),
        "taxon": ("taxon__taxon_name", "pipeline_run__run_id", "sequence_name", "sequence_id"),
        "-taxon": ("-taxon__taxon_name", "pipeline_run__run_id", "sequence_name", "sequence_id"),
        "run": ("pipeline_run__run_id", "sequence_name", "sequence_id"),
        "-run": ("-pipeline_run__run_id", "sequence_name", "sequence_id"),
        "proteins": ("-proteins_count", "pipeline_run__run_id", "sequence_name", "sequence_id"),
        "-proteins": ("proteins_count", "pipeline_run__run_id", "sequence_name", "sequence_id"),
        "calls": ("-repeat_calls_count", "pipeline_run__run_id", "sequence_name", "sequence_id"),
        "-calls": ("repeat_calls_count", "pipeline_run__run_id", "sequence_name", "sequence_id"),
    }
    default_ordering = ("pipeline_run_id", "assembly_accession", "sequence_name", "id")

    def get_base_queryset(self):
        return _annotated_sequences(
            Sequence.objects.select_related("pipeline_run", "taxon")
            .defer("nucleotide_sequence")
            .only(
                "id",
                "pipeline_run_id",
                "pipeline_run__id",
                "pipeline_run__run_id",
                "genome_id",
                "taxon_id",
                "taxon__id",
                "taxon__taxon_name",
                "sequence_id",
                "sequence_name",
                "sequence_length",
                "gene_symbol",
                "assembly_accession",
            )
        )

    def include_virtual_scroll_count(self, *, context=None, page_obj=None):
        return False

    def use_cursor_pagination(self, queryset):
        return hasattr(queryset, "filter") and self.uses_fast_default_ordering()

    def _load_filter_state(self):
        self.current_run = _resolve_current_run(self.request)
        self.branch_scope = _resolve_branch_scope(self.request)
        self.selected_branch_taxon = self.branch_scope["selected_branch_taxon"]
        self.current_accession = self.request.GET.get("accession", "").strip()
        self.current_gene_symbol = self.request.GET.get("gene_symbol", "").strip()
        self.current_genome = self.request.GET.get("genome", "").strip()

    def apply_search(self, queryset):
        query = self.get_search_query()
        if not query:
            return queryset

        return queryset.filter(
            Q(sequence_id__istartswith=query)
            | Q(sequence_name__istartswith=query)
            | Q(gene_symbol__istartswith=query)
            | Q(assembly_accession__istartswith=query)
        )

    def apply_filters(self, queryset):
        self._load_filter_state()

        if self.current_run:
            queryset = queryset.filter(pipeline_run=self.current_run)

        queryset = _apply_branch_scope_filter(queryset, branch_scope=self.branch_scope, field_name="taxon_id")

        if self.current_accession:
            queryset = queryset.filter(
                Q(assembly_accession__istartswith=self.current_accession)
                | Q(genome__accession__istartswith=self.current_accession)
            )

        if self.current_gene_symbol:
            queryset = queryset.filter(gene_symbol__istartswith=self.current_gene_symbol)

        if self.current_genome:
            queryset = queryset.filter(genome__genome_id=self.current_genome)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.is_virtual_scroll_fragment_request():
            return context
        current_run = getattr(self, "current_run", None)
        context["current_run"] = current_run
        context["current_run_id"] = current_run.run_id if current_run else ""
        context["run_choices"] = PipelineRun.objects.order_by("-imported_at", "run_id")
        _update_branch_scope_context(context, getattr(self, "branch_scope", _resolve_branch_scope(self.request)))
        context["current_accession"] = getattr(self, "current_accession", "")
        context["current_gene_symbol"] = getattr(self, "current_gene_symbol", "")
        context["current_genome"] = getattr(self, "current_genome", "")
        context["selected_genome"] = _resolve_genome_filter(current_run, context["current_genome"])
        return context


class SequenceDetailView(DetailView):
    model = Sequence
    template_name = "browser/sequence_detail.html"
    context_object_name = "sequence"

    def get_queryset(self):
        return Sequence.objects.select_related("pipeline_run", "genome", "taxon")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sequence = self.object
        proteins = sequence.proteins.order_by("protein_name", "protein_id")
        repeat_calls = sequence.repeat_calls.select_related("protein").order_by("protein__protein_name", "start", "call_id")

        context["proteins_count"] = proteins.count()
        context["repeat_calls_count"] = repeat_calls.count()
        context["protein_preview"] = proteins[:12]
        context["repeat_call_preview"] = repeat_calls[:12]
        context["taxon_detail_url"] = _url_with_query(
            reverse("browser:taxon-detail", args=[sequence.taxon.pk]),
            run=sequence.pipeline_run.run_id,
        )
        context["protein_browser_url"] = _url_with_query(
            reverse("browser:protein-list"),
            run=sequence.pipeline_run.run_id,
            sequence=sequence.sequence_id,
        )
        context["repeatcall_browser_url"] = _url_with_query(
            reverse("browser:repeatcall-list"),
            run=sequence.pipeline_run.run_id,
            sequence=sequence.sequence_id,
        )
        context["sequence_list_url"] = _url_with_query(
            reverse("browser:sequence-list"),
            run=sequence.pipeline_run.run_id,
            genome=sequence.genome.genome_id,
        )
        context["run_detail_url"] = reverse("browser:run-detail", args=[sequence.pipeline_run.pk])
        return context
