from django.urls import reverse
from django.views.generic import DetailView

from ..merged import accession_group_queryset
from ..models import Genome, PipelineRun, TaxonClosure
from .filters import (
    _apply_branch_scope_filter,
    _resolve_browser_mode,
    _resolve_branch_scope,
    _resolve_current_run,
    _update_branch_scope_context,
)
from .formatting import _ordering_label
from .navigation import _url_with_query
from .pagination import VirtualScrollListView
from .querysets import _annotated_genomes


class GenomeListView(VirtualScrollListView):
    model = Genome
    template_name = "browser/genome_list.html"
    context_object_name = "genomes"
    virtual_scroll_row_template_name = "browser/includes/genome_list_rows.html"
    merged_ordering_map = {
        "accession": ("accession",),
        "-accession": ("-accession",),
        "source_genomes": ("-source_genomes_count", "accession"),
        "-source_genomes": ("source_genomes_count", "accession"),
        "source_runs": ("-source_runs_count", "accession"),
        "-source_runs": ("source_runs_count", "accession"),
        "raw_repeat_calls": ("-raw_repeat_calls_count", "accession"),
        "-raw_repeat_calls": ("raw_repeat_calls_count", "accession"),
        "proteins": ("-raw_repeat_calls_count", "accession"),
        "-proteins": ("raw_repeat_calls_count", "accession"),
        "analyzed_proteins": ("-analyzed_protein_max", "-analyzed_protein_min", "accession"),
        "-analyzed_proteins": ("analyzed_protein_min", "analyzed_protein_max", "accession"),
    }
    merged_default_ordering = ("accession",)
    ordering_map = {
        "accession": ("pipeline_run__run_id", "accession", "genome_id"),
        "-accession": ("pipeline_run__run_id", "-accession", "genome_id"),
        "genome_name": ("pipeline_run__run_id", "genome_name", "accession", "genome_id"),
        "-genome_name": ("pipeline_run__run_id", "-genome_name", "accession", "genome_id"),
        "taxon": ("taxon__taxon_name", "pipeline_run__run_id", "accession", "genome_id"),
        "-taxon": ("-taxon__taxon_name", "pipeline_run__run_id", "accession", "genome_id"),
        "run": ("pipeline_run__run_id", "accession", "genome_id"),
        "-run": ("-pipeline_run__run_id", "accession", "genome_id"),
        "sequences": ("-sequences_count", "pipeline_run__run_id", "accession", "genome_id"),
        "-sequences": ("sequences_count", "pipeline_run__run_id", "accession", "genome_id"),
        "proteins": ("-proteins_count", "pipeline_run__run_id", "accession", "genome_id"),
        "-proteins": ("proteins_count", "pipeline_run__run_id", "accession", "genome_id"),
        "repeat_calls": ("-repeat_calls_count", "pipeline_run__run_id", "accession", "genome_id"),
        "-repeat_calls": ("repeat_calls_count", "pipeline_run__run_id", "accession", "genome_id"),
    }
    default_ordering = ("pipeline_run__run_id", "accession", "genome_id")

    def get_virtual_scroll_colspan(self, context):
        return 5 if context.get("current_mode") == "merged" else 7

    def get_base_queryset(self):
        return _annotated_genomes(
            Genome.objects.select_related("pipeline_run", "taxon").only(
                "id",
                "pipeline_run_id",
                "pipeline_run__id",
                "pipeline_run__run_id",
                "taxon_id",
                "taxon__id",
                "taxon__taxon_name",
                "genome_id",
                "accession",
                "genome_name",
            )
        )

    def _load_filter_state(self):
        self.current_run = _resolve_current_run(self.request)
        self.branch_scope = _resolve_branch_scope(self.request)
        self.selected_branch_taxon = self.branch_scope["selected_branch_taxon"]
        self.current_accession = self.request.GET.get("accession", "").strip()
        self.current_genome_name = self.request.GET.get("genome_name", "").strip()
        self.current_mode = _resolve_browser_mode(self.request)

    def apply_filters(self, queryset):
        self._load_filter_state()

        if self.current_run:
            queryset = queryset.filter(pipeline_run=self.current_run)

        queryset = _apply_branch_scope_filter(queryset, branch_scope=self.branch_scope, field_name="taxon_id")

        if self.current_accession:
            queryset = queryset.filter(accession__istartswith=self.current_accession)

        if self.current_genome_name:
            queryset = queryset.filter(genome_name__istartswith=self.current_genome_name)

        return queryset

    def get_queryset(self):
        self._load_filter_state()
        if self.current_mode == "merged":
            queryset = accession_group_queryset(
                current_run=self.current_run,
                accession_query=self.current_accession,
                genome_name=self.current_genome_name,
                branch_taxon=self.selected_branch_taxon,
                branch_taxa_ids=self.branch_scope["branch_taxa_ids"],
            )
            requested_ordering = self.request.GET.get("order_by", "").strip()
            ordering = self.merged_ordering_map.get(requested_ordering, self.merged_default_ordering)
            if ordering:
                queryset = queryset.order_by(*ordering)
            return queryset
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_run = getattr(self, "current_run", None)
        context["current_run"] = current_run
        context["current_run_id"] = current_run.run_id if current_run else ""
        context["current_mode"] = getattr(self, "current_mode", "run")
        context["run_choices"] = PipelineRun.objects.order_by("-imported_at", "run_id")
        _update_branch_scope_context(context, getattr(self, "branch_scope", _resolve_branch_scope(self.request)))
        context["current_accession"] = getattr(self, "current_accession", "")
        context["current_genome_name"] = getattr(self, "current_genome_name", "")
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


class GenomeDetailView(DetailView):
    model = Genome
    template_name = "browser/genome_detail.html"
    context_object_name = "genome"

    def get_queryset(self):
        return Genome.objects.select_related("pipeline_run", "taxon")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        genome = self.object
        proteins = genome.proteins.order_by("protein_name", "protein_id")
        repeat_calls = genome.repeat_calls.select_related("protein").order_by("protein__protein_name", "start", "call_id")

        context["lineage"] = (
            TaxonClosure.objects.filter(descendant=genome.taxon)
            .select_related("ancestor")
            .order_by("-depth", "ancestor__taxon_name")
        )
        context["sequences_count"] = genome.sequences.count()
        context["proteins_count"] = proteins.count()
        context["repeat_calls_count"] = repeat_calls.count()
        context["protein_preview"] = proteins[:10]
        context["repeat_call_preview"] = repeat_calls[:10]
        context["taxon_detail_url"] = _url_with_query(
            reverse("browser:taxon-detail", args=[genome.taxon.pk]),
            run=genome.pipeline_run.run_id,
        )
        context["protein_browser_url"] = _url_with_query(
            reverse("browser:protein-list"),
            run=genome.pipeline_run.run_id,
            genome=genome.genome_id,
        )
        context["sequence_browser_url"] = _url_with_query(
            reverse("browser:sequence-list"),
            run=genome.pipeline_run.run_id,
            genome=genome.genome_id,
        )
        context["repeatcall_browser_url"] = _url_with_query(
            reverse("browser:repeatcall-list"),
            run=genome.pipeline_run.run_id,
            genome=genome.genome_id,
        )
        context["merged_accession_url"] = reverse("browser:accession-detail", args=[genome.accession])
        context["related_accession_genomes_count"] = Genome.objects.filter(accession=genome.accession).count()
        context["run_detail_url"] = reverse("browser:run-detail", args=[genome.pipeline_run.pk])
        return context
