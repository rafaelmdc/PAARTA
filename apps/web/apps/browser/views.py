from django.db.models import Count, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.views.generic import DetailView, ListView, TemplateView

from .models import Genome, PipelineRun, Protein, RepeatCall, RunParameter, Sequence, Taxon


class BrowserHomeView(TemplateView):
    template_name = "browser/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cards"] = [
            {
                "title": "Imported runs",
                "count": PipelineRun.objects.count(),
                "description": "Browse imported pipeline runs and inspect their provenance and counts.",
                "url_name": "browser:run-list",
            },
            {
                "title": "Taxa",
                "count": Taxon.objects.count(),
                "description": "Lineage-aware taxon browser backed by imported taxonomy and closure rows.",
                "url_name": "browser:taxon-list",
            },
            {
                "title": "Genomes",
                "count": Genome.objects.count(),
                "description": "Genome-level browser with accession-aware identity and run provenance.",
                "url_name": "browser:genome-list",
            },
            {
                "title": "Proteins",
                "count": Protein.objects.count(),
                "description": "Protein browser keyed to imported translations and linked repeat calls.",
                "url_name": "browser:protein-list",
            },
            {
                "title": "Repeat calls",
                "count": RepeatCall.objects.count(),
                "description": "Canonical merged repeat-call records with run and protein provenance.",
                "url_name": "browser:repeatcall-list",
            },
        ]
        context["recent_runs"] = _annotated_runs()[:5]
        return context


class BrowserListView(ListView):
    paginate_by = 20
    ordering_map = {}
    default_ordering = ()
    search_fields = ()

    def get_search_query(self):
        return self.request.GET.get("q", "").strip()

    def get_ordering(self):
        requested_ordering = self.request.GET.get("order_by", "").strip()
        if requested_ordering in self.ordering_map:
            return self.ordering_map[requested_ordering]
        return self.default_ordering

    def apply_search(self, queryset):
        query = self.get_search_query()
        if not query or not self.search_fields:
            return queryset

        search_filter = Q()
        for field_name in self.search_fields:
            search_filter |= Q(**{f"{field_name}__icontains": query})
        return queryset.filter(search_filter)

    def apply_filters(self, queryset):
        return queryset

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.apply_search(queryset)
        queryset = self.apply_filters(queryset)
        ordering = self.get_ordering()
        if ordering:
            queryset = queryset.order_by(*ordering)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_query"] = self.get_search_query()
        context["current_order_by"] = self.request.GET.get("order_by", "").strip()
        context["ordering_options"] = [
            {"value": value, "label": _ordering_label(value)}
            for value in self.ordering_map.keys()
        ]
        page_query = self.request.GET.copy()
        page_query.pop("page", None)
        context["page_query"] = page_query.urlencode()
        return context


class RunListView(BrowserListView):
    model = PipelineRun
    template_name = "browser/run_list.html"
    context_object_name = "runs"
    search_fields = ("run_id", "status", "profile", "git_revision")
    ordering_map = {
        "run_id": ("run_id",),
        "-run_id": ("-run_id",),
        "started": ("started_at_utc", "run_id"),
        "-started": ("-started_at_utc", "run_id"),
        "finished": ("finished_at_utc", "run_id"),
        "-finished": ("-finished_at_utc", "run_id"),
        "imported": ("imported_at", "run_id"),
        "-imported": ("-imported_at", "run_id"),
    }
    default_ordering = ("-imported_at", "run_id")

    def apply_filters(self, queryset):
        status = self.request.GET.get("status", "").strip()
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_queryset(self):
        queryset = super().get_queryset()
        return _annotated_runs(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_status"] = self.request.GET.get("status", "").strip()
        context["status_choices"] = PipelineRun.objects.order_by("status").values_list("status", flat=True).distinct()
        return context


class RunDetailView(DetailView):
    model = PipelineRun
    template_name = "browser/run_detail.html"
    context_object_name = "pipeline_run"

    def get_queryset(self):
        return _annotated_runs()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pipeline_run = self.object
        context["distinct_taxa_count"] = _run_distinct_taxa_count(pipeline_run)
        context["linked_sections"] = [
            {
                "title": "Taxa",
                "description": "Lineage-aware taxon view scoped to this run.",
                "url_name": "browser:taxon-list",
            },
            {
                "title": "Genomes",
                "description": "Genome-level browser scoped to this run.",
                "url_name": "browser:genome-list",
            },
            {
                "title": "Proteins",
                "description": "Protein-level browser scoped to this run.",
                "url_name": "browser:protein-list",
            },
            {
                "title": "Repeat calls",
                "description": "Canonical repeat-call browser scoped to this run.",
                "url_name": "browser:repeatcall-list",
            },
        ]
        context["methods"] = list(
            pipeline_run.run_parameters.order_by("method", "param_name").values_list("method", flat=True).distinct()
        )
        context["repeat_residues"] = list(
            pipeline_run.repeat_calls.order_by("repeat_residue").values_list("repeat_residue", flat=True).distinct()
        )
        context["latest_import_batch"] = pipeline_run.import_batches.order_by("-started_at").first()
        return context


class BrowserSectionPlaceholderView(TemplateView):
    template_name = "browser/section_placeholder.html"
    title = ""
    description = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_run_id = self.request.GET.get("run", "").strip()
        current_run = None
        if current_run_id:
            current_run = PipelineRun.objects.filter(run_id=current_run_id).first()
        context["section_title"] = self.title
        context["section_description"] = self.description
        context["current_run"] = current_run
        context["current_run_id"] = current_run_id
        return context


class TaxonListPlaceholderView(BrowserSectionPlaceholderView):
    title = "Taxa"
    description = "The lineage-aware taxon browser lands in the next slice."


class GenomeListPlaceholderView(BrowserSectionPlaceholderView):
    title = "Genomes"
    description = "The accession-aware genome browser lands in the next slice."


class ProteinListPlaceholderView(BrowserSectionPlaceholderView):
    title = "Proteins"
    description = "The protein browser lands after taxa and genomes are in place."


class RepeatCallListPlaceholderView(BrowserSectionPlaceholderView):
    title = "Repeat calls"
    description = "The canonical repeat-call browser lands after the protein browser."


def _annotated_runs(queryset=None):
    if queryset is None:
        queryset = PipelineRun.objects.all()
    return queryset.annotate(
        genomes_count=Coalesce(_count_subquery(Genome), Value(0)),
        sequences_count=Coalesce(_count_subquery(Sequence), Value(0)),
        proteins_count=Coalesce(_count_subquery(Protein), Value(0)),
        repeat_calls_count=Coalesce(_count_subquery(RepeatCall), Value(0)),
        run_parameters_count=Coalesce(_count_subquery(RunParameter), Value(0)),
    )


def _run_distinct_taxa_count(pipeline_run: PipelineRun) -> int:
    taxon_ids = Genome.objects.filter(pipeline_run=pipeline_run).order_by().values_list("taxon_id", flat=True).union(
        Sequence.objects.filter(pipeline_run=pipeline_run).order_by().values_list("taxon_id", flat=True),
        Protein.objects.filter(pipeline_run=pipeline_run).order_by().values_list("taxon_id", flat=True),
        RepeatCall.objects.filter(pipeline_run=pipeline_run).order_by().values_list("taxon_id", flat=True),
    )
    return taxon_ids.count()


def _count_subquery(model):
    return Subquery(
        model.objects.filter(pipeline_run=OuterRef("pk"))
        .order_by()
        .values("pipeline_run")
        .annotate(total=Count("pk"))
        .values("total")[:1],
        output_field=IntegerField(),
    )


def _ordering_label(value: str) -> str:
    direction = "ascending"
    field_name = value
    if value.startswith("-"):
        direction = "descending"
        field_name = value[1:]
    return f"{field_name.replace('_', ' ').title()} ({direction})"
