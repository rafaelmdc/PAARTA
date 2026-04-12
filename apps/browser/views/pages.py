from importlib import import_module

from django.db.models import Count, Exists, Max, Min, OuterRef, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import Http404
from django.urls import reverse
from django.views.generic import DetailView, TemplateView

from apps.imports.models import ImportBatch

from ..merged import (
    accession_group_queryset,
    build_accession_summary,
    build_accession_analytics,
    merged_protein_groups,
    merged_repeat_call_groups,
)
from ..metadata import resolve_run_browser_metadata
from ..models import (
    AccessionCallCount,
    AccessionStatus,
    AcquisitionBatch,
    DownloadManifestEntry,
    Genome,
    NormalizationWarning,
    PipelineRun,
    Protein,
    RepeatCall,
    Sequence,
    Taxon,
    TaxonClosure,
)
from .filters import (
    _apply_branch_scope_filter,
    _branch_taxon_ids,
    _repeat_call_filter_q,
    _resolve_batch_filter,
    _resolve_browser_mode,
    _resolve_branch_scope,
    _resolve_current_run,
    _resolve_genome_filter,
    _resolve_protein_filter,
    _resolve_sequence_filter,
    _run_distinct_taxa_count,
    _run_import_batches,
    _run_taxon_ids,
    _scoped_repeat_calls,
    _update_branch_scope_context,
)
from .formatting import (
    _mapping_items,
    _ordering_label,
    _parse_float,
    _parse_positive_int,
    _sort_dict_records,
)
from .navigation import _browser_directory_sections, _url_with_query
from .pagination import VirtualScrollListView
from .querysets import (
    _annotated_batches,
    _annotated_genomes,
    _annotated_proteins,
    _annotated_runs,
    _annotated_sequences,
    _summary_runs,
)


class BrowserHomeView(TemplateView):
    template_name = "browser/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["directory_sections"] = _browser_directory_sections()
        context["recent_runs"] = _summary_runs()[:5]
        return context


def resolve_browser_facets(*, pipeline_run=None, pipeline_runs=None):
    return import_module(__package__).resolve_browser_facets(
        pipeline_run=pipeline_run,
        pipeline_runs=pipeline_runs,
    )


class RunListView(VirtualScrollListView):
    model = PipelineRun
    template_name = "browser/run_list.html"
    context_object_name = "runs"
    virtual_scroll_row_template_name = "browser/includes/run_list_rows.html"
    virtual_scroll_colspan = 8
    search_fields = ("run_id", "status", "profile", "git_revision")
    ordering_map = {
        "run_id": ("run_id",),
        "-run_id": ("-run_id",),
        "status": ("status", "run_id"),
        "-status": ("-status", "run_id"),
        "profile": ("profile", "run_id"),
        "-profile": ("-profile", "run_id"),
        "genomes": ("-genomes_count", "run_id"),
        "-genomes": ("genomes_count", "run_id"),
        "sequences": ("-sequences_count", "run_id"),
        "-sequences": ("sequences_count", "run_id"),
        "proteins": ("-proteins_count", "run_id"),
        "-proteins": ("proteins_count", "run_id"),
        "repeat_calls": ("-repeat_calls_count", "run_id"),
        "-repeat_calls": ("repeat_calls_count", "run_id"),
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

    def get_base_queryset(self):
        return _summary_runs()

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
        import_batches = _run_import_batches(pipeline_run)
        active_import_batch = import_batches.filter(
            status__in=[ImportBatch.Status.PENDING, ImportBatch.Status.RUNNING]
        ).order_by("-started_at", "-pk").first()
        latest_import_batch = import_batches.order_by("-started_at", "-pk").first()
        latest_completed_import_batch = import_batches.filter(status=ImportBatch.Status.COMPLETED).order_by(
            "-finished_at",
            "-started_at",
            "-pk",
        ).first()
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
                "title": "Sequences",
                "description": "Call-linked sequence subset stored for browsing and provenance.",
                "url_name": "browser:sequence-list",
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
            {
                "title": "Accession status",
                "description": "Accession-level operational status rows imported for this run.",
                "url_name": "browser:accessionstatus-list",
            },
            {
                "title": "Method/residue status",
                "description": "Per-accession method and residue call-count rows imported for this run.",
                "url_name": "browser:accessioncallcount-list",
            },
            {
                "title": "Download manifest",
                "description": "Batch-scoped download provenance rows imported from raw acquisition outputs.",
                "url_name": "browser:downloadmanifest-list",
            },
            {
                "title": "Normalization warnings",
                "description": "Operational warning rows imported from raw acquisition and normalization outputs.",
                "url_name": "browser:normalizationwarning-list",
            },
        ]
        run_facets = resolve_run_browser_metadata(pipeline_run)["facets"]
        context["methods"] = run_facets["methods"]
        context["repeat_residues"] = run_facets["residues"]
        context["method_residue_summary"] = list(
            pipeline_run.accession_call_count_rows.values("method", "repeat_residue")
            .annotate(
                accession_total=Count("pk"),
                repeat_calls_total=Coalesce(Sum("n_repeat_calls"), Value(0)),
            )
            .order_by("method", "repeat_residue")
        )
        context["terminal_status_summary"] = list(
            pipeline_run.accession_status_rows.values("terminal_status")
            .annotate(total=Count("pk"))
            .order_by("terminal_status")
        )
        context["warning_summary"] = list(
            pipeline_run.normalization_warnings.values("warning_code", "warning_scope")
            .annotate(total=Count("pk"))
            .order_by("-total", "warning_code", "warning_scope")
        )
        context["warning_browser_url"] = _url_with_query(
            reverse("browser:normalizationwarning-list"),
            run=pipeline_run.run_id,
        )
        context["taxon_browser_url"] = _url_with_query(
            reverse("browser:taxon-list"),
            run=pipeline_run.run_id,
        )
        context["genome_browser_url"] = _url_with_query(
            reverse("browser:genome-list"),
            run=pipeline_run.run_id,
        )
        context["protein_browser_url"] = _url_with_query(
            reverse("browser:protein-list"),
            run=pipeline_run.run_id,
        )
        context["repeatcall_browser_url"] = _url_with_query(
            reverse("browser:repeatcall-list"),
            run=pipeline_run.run_id,
        )
        context["accession_browser_url"] = _url_with_query(
            reverse("browser:accession-list"),
            run=pipeline_run.run_id,
        )
        context["merged_protein_browser_url"] = _url_with_query(
            reverse("browser:protein-list"),
            run=pipeline_run.run_id,
            mode="merged",
        )
        context["merged_repeatcall_browser_url"] = _url_with_query(
            reverse("browser:repeatcall-list"),
            run=pipeline_run.run_id,
            mode="merged",
        )
        context["accession_status_browser_url"] = _url_with_query(
            reverse("browser:accessionstatus-list"),
            run=pipeline_run.run_id,
        )
        context["accession_call_count_browser_url"] = _url_with_query(
            reverse("browser:accessioncallcount-list"),
            run=pipeline_run.run_id,
        )
        context["download_manifest_browser_url"] = _url_with_query(
            reverse("browser:downloadmanifest-list"),
            run=pipeline_run.run_id,
        )
        context["batch_preview"] = _annotated_batches(
            pipeline_run.acquisition_batches.order_by("batch_id")
        )[:12]
        context["batch_preview_is_truncated"] = pipeline_run.acquisition_batches_count > len(context["batch_preview"])
        context["active_import_batch"] = active_import_batch
        context["active_import_progress_items"] = _mapping_items(
            active_import_batch.progress_payload if active_import_batch else {},
            exclude_keys={"message"},
        )
        context["latest_import_batch"] = latest_import_batch
        context["latest_completed_import_batch"] = latest_completed_import_batch
        context["latest_import_row_count_items"] = _mapping_items(
            latest_completed_import_batch.row_counts if latest_completed_import_batch else {}
        )
        context["recent_import_batches"] = list(import_batches.order_by("-started_at", "-pk")[:5])
        context["imports_history_url"] = reverse("imports:history")
        return context


class NormalizationWarningListView(VirtualScrollListView):
    model = NormalizationWarning
    template_name = "browser/normalizationwarning_list.html"
    context_object_name = "warnings"
    virtual_scroll_row_template_name = "browser/includes/normalizationwarning_list_rows.html"
    virtual_scroll_colspan = 8
    search_fields = (
        "warning_code",
        "warning_message",
        "assembly_accession",
        "genome_id",
        "sequence_id",
        "protein_id",
        "source_record_id",
    )
    ordering_map = {
        "warning_code": ("warning_code", "pipeline_run__run_id", "batch__batch_id", "assembly_accession"),
        "-warning_code": ("-warning_code", "pipeline_run__run_id", "batch__batch_id", "assembly_accession"),
        "warning_scope": ("warning_scope", "warning_code", "pipeline_run__run_id", "batch__batch_id"),
        "-warning_scope": ("-warning_scope", "warning_code", "pipeline_run__run_id", "batch__batch_id"),
        "accession": ("assembly_accession", "warning_code", "pipeline_run__run_id", "batch__batch_id"),
        "-accession": ("-assembly_accession", "warning_code", "pipeline_run__run_id", "batch__batch_id"),
        "batch": ("batch__batch_id", "warning_code", "assembly_accession"),
        "-batch": ("-batch__batch_id", "warning_code", "assembly_accession"),
        "genome": ("genome_id", "warning_code", "assembly_accession", "pipeline_run__run_id"),
        "-genome": ("-genome_id", "warning_code", "assembly_accession", "pipeline_run__run_id"),
        "sequence": ("sequence_id", "warning_code", "assembly_accession", "pipeline_run__run_id"),
        "-sequence": ("-sequence_id", "warning_code", "assembly_accession", "pipeline_run__run_id"),
        "protein": ("protein_id", "warning_code", "assembly_accession", "pipeline_run__run_id"),
        "-protein": ("-protein_id", "warning_code", "assembly_accession", "pipeline_run__run_id"),
        "run": ("pipeline_run__run_id", "batch__batch_id", "warning_code", "assembly_accession"),
        "-run": ("-pipeline_run__run_id", "batch__batch_id", "warning_code", "assembly_accession"),
        "message": ("warning_message", "warning_code", "assembly_accession", "pipeline_run__run_id"),
        "-message": ("-warning_message", "warning_code", "assembly_accession", "pipeline_run__run_id"),
    }
    default_ordering = ("pipeline_run__run_id", "batch__batch_id", "warning_code", "assembly_accession")

    def get_base_queryset(self):
        return NormalizationWarning.objects.select_related("pipeline_run", "batch")

    def _load_filter_state(self):
        self.current_run = _resolve_current_run(self.request)
        self.current_batch = self.request.GET.get("batch", "").strip()
        self.current_accession = self.request.GET.get("accession", "").strip()
        self.current_warning_code = self.request.GET.get("warning_code", "").strip()
        self.current_warning_scope = self.request.GET.get("warning_scope", "").strip()

    def apply_filters(self, queryset):
        self._load_filter_state()

        if self.current_run:
            queryset = queryset.filter(pipeline_run=self.current_run)

        if self.current_batch:
            queryset = queryset.filter(batch__pk=self.current_batch)

        if self.current_accession:
            queryset = queryset.filter(assembly_accession__icontains=self.current_accession)

        if self.current_warning_code:
            queryset = queryset.filter(warning_code=self.current_warning_code)

        if self.current_warning_scope:
            queryset = queryset.filter(warning_scope=self.current_warning_scope)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_run = getattr(self, "current_run", None)
        current_batch = getattr(self, "current_batch", "")

        filter_choices = NormalizationWarning.objects.all()
        batch_choices = AcquisitionBatch.objects.select_related("pipeline_run")
        if current_run:
            filter_choices = filter_choices.filter(pipeline_run=current_run)
            batch_choices = batch_choices.filter(pipeline_run=current_run)
        if current_batch:
            filter_choices = filter_choices.filter(batch__pk=current_batch)

        context["current_run"] = current_run
        context["current_run_id"] = current_run.run_id if current_run else ""
        context["selected_batch"] = _resolve_batch_filter(current_run, current_batch)
        context["current_batch"] = current_batch
        context["current_accession"] = getattr(self, "current_accession", "")
        context["current_warning_code"] = getattr(self, "current_warning_code", "")
        context["current_warning_scope"] = getattr(self, "current_warning_scope", "")
        context["run_choices"] = PipelineRun.objects.order_by("-imported_at", "run_id")
        context["batch_choices"] = batch_choices.order_by("pipeline_run__run_id", "batch_id")
        context["warning_code_choices"] = filter_choices.order_by("warning_code").values_list(
            "warning_code",
            flat=True,
        ).distinct()
        context["warning_scope_choices"] = (
            filter_choices.exclude(warning_scope="")
            .order_by("warning_scope")
            .values_list("warning_scope", flat=True)
            .distinct()
        )
        return context


class AccessionStatusListView(VirtualScrollListView):
    model = AccessionStatus
    template_name = "browser/accessionstatus_list.html"
    context_object_name = "status_rows"
    virtual_scroll_row_template_name = "browser/includes/accessionstatus_list_rows.html"
    virtual_scroll_colspan = 10
    search_fields = ("assembly_accession", "failure_stage", "failure_reason", "notes")
    ordering_map = {
        "accession": ("assembly_accession", "pipeline_run__run_id", "batch__batch_id"),
        "-accession": ("-assembly_accession", "pipeline_run__run_id", "batch__batch_id"),
        "batch": ("batch__batch_id", "assembly_accession"),
        "-batch": ("-batch__batch_id", "assembly_accession"),
        "download_status": ("download_status", "assembly_accession"),
        "-download_status": ("-download_status", "assembly_accession"),
        "normalize_status": ("normalize_status", "assembly_accession"),
        "-normalize_status": ("-normalize_status", "assembly_accession"),
        "translate_status": ("translate_status", "assembly_accession"),
        "-translate_status": ("-translate_status", "assembly_accession"),
        "detect_status": ("detect_status", "assembly_accession"),
        "-detect_status": ("-detect_status", "assembly_accession"),
        "finalize_status": ("finalize_status", "assembly_accession"),
        "-finalize_status": ("-finalize_status", "assembly_accession"),
        "run": ("pipeline_run__run_id", "batch__batch_id", "assembly_accession"),
        "-run": ("-pipeline_run__run_id", "batch__batch_id", "assembly_accession"),
        "terminal_status": ("terminal_status", "assembly_accession"),
        "-terminal_status": ("-terminal_status", "assembly_accession"),
        "repeat_calls": ("-n_repeat_calls", "assembly_accession"),
        "-repeat_calls": ("n_repeat_calls", "assembly_accession"),
    }
    default_ordering = ("pipeline_run__run_id", "batch__batch_id", "assembly_accession")

    def get_base_queryset(self):
        return AccessionStatus.objects.select_related("pipeline_run", "batch")

    def _load_filter_state(self):
        self.current_run = _resolve_current_run(self.request)
        self.current_batch = self.request.GET.get("batch", "").strip()
        self.current_accession = self.request.GET.get("accession", "").strip()
        self.current_terminal_status = self.request.GET.get("terminal_status", "").strip()
        self.current_detect_status = self.request.GET.get("detect_status", "").strip()
        self.current_finalize_status = self.request.GET.get("finalize_status", "").strip()

    def apply_filters(self, queryset):
        self._load_filter_state()

        if self.current_run:
            queryset = queryset.filter(pipeline_run=self.current_run)

        if self.current_batch:
            queryset = queryset.filter(batch__pk=self.current_batch)

        if self.current_accession:
            queryset = queryset.filter(assembly_accession__icontains=self.current_accession)

        if self.current_terminal_status:
            queryset = queryset.filter(terminal_status=self.current_terminal_status)

        if self.current_detect_status:
            queryset = queryset.filter(detect_status=self.current_detect_status)

        if self.current_finalize_status:
            queryset = queryset.filter(finalize_status=self.current_finalize_status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_run = getattr(self, "current_run", None)
        current_batch = getattr(self, "current_batch", "")

        filter_choices = AccessionStatus.objects.all()
        batch_choices = AcquisitionBatch.objects.select_related("pipeline_run")
        if current_run:
            filter_choices = filter_choices.filter(pipeline_run=current_run)
            batch_choices = batch_choices.filter(pipeline_run=current_run)
        if current_batch:
            filter_choices = filter_choices.filter(batch__pk=current_batch)

        context["current_run"] = current_run
        context["current_run_id"] = current_run.run_id if current_run else ""
        context["selected_batch"] = _resolve_batch_filter(current_run, current_batch)
        context["current_batch"] = current_batch
        context["current_accession"] = getattr(self, "current_accession", "")
        context["current_terminal_status"] = getattr(self, "current_terminal_status", "")
        context["current_detect_status"] = getattr(self, "current_detect_status", "")
        context["current_finalize_status"] = getattr(self, "current_finalize_status", "")
        context["run_choices"] = PipelineRun.objects.order_by("-imported_at", "run_id")
        context["batch_choices"] = batch_choices.order_by("pipeline_run__run_id", "batch_id")
        context["terminal_status_choices"] = (
            filter_choices.exclude(terminal_status="")
            .order_by("terminal_status")
            .values_list("terminal_status", flat=True)
            .distinct()
        )
        context["detect_status_choices"] = (
            filter_choices.exclude(detect_status="")
            .order_by("detect_status")
            .values_list("detect_status", flat=True)
            .distinct()
        )
        context["finalize_status_choices"] = (
            filter_choices.exclude(finalize_status="")
            .order_by("finalize_status")
            .values_list("finalize_status", flat=True)
            .distinct()
        )
        return context


class AccessionCallCountListView(VirtualScrollListView):
    model = AccessionCallCount
    template_name = "browser/accessioncallcount_list.html"
    context_object_name = "call_count_rows"
    virtual_scroll_row_template_name = "browser/includes/accessioncallcount_list_rows.html"
    virtual_scroll_colspan = 8
    search_fields = ("assembly_accession",)
    ordering_map = {
        "accession": ("assembly_accession", "method", "repeat_residue"),
        "-accession": ("-assembly_accession", "method", "repeat_residue"),
        "batch": ("batch__batch_id", "assembly_accession", "method", "repeat_residue"),
        "-batch": ("-batch__batch_id", "assembly_accession", "method", "repeat_residue"),
        "run": ("pipeline_run__run_id", "batch__batch_id", "assembly_accession"),
        "-run": ("-pipeline_run__run_id", "batch__batch_id", "assembly_accession"),
        "method": ("method", "repeat_residue", "assembly_accession"),
        "-method": ("-method", "repeat_residue", "assembly_accession"),
        "residue": ("repeat_residue", "method", "assembly_accession"),
        "-residue": ("-repeat_residue", "method", "assembly_accession"),
        "detect_status": ("detect_status", "assembly_accession", "method", "repeat_residue"),
        "-detect_status": ("-detect_status", "assembly_accession", "method", "repeat_residue"),
        "finalize_status": ("finalize_status", "assembly_accession", "method", "repeat_residue"),
        "-finalize_status": ("-finalize_status", "assembly_accession", "method", "repeat_residue"),
        "repeat_calls": ("-n_repeat_calls", "assembly_accession", "method", "repeat_residue"),
        "-repeat_calls": ("n_repeat_calls", "assembly_accession", "method", "repeat_residue"),
    }
    default_ordering = ("pipeline_run__run_id", "batch__batch_id", "assembly_accession", "method", "repeat_residue")

    def get_base_queryset(self):
        return AccessionCallCount.objects.select_related("pipeline_run", "batch")

    def _load_filter_state(self):
        self.current_run = _resolve_current_run(self.request)
        self.current_batch = self.request.GET.get("batch", "").strip()
        self.current_accession = self.request.GET.get("accession", "").strip()
        self.current_method = self.request.GET.get("method", "").strip()
        self.current_residue = self.request.GET.get("residue", "").strip().upper()
        self.current_detect_status = self.request.GET.get("detect_status", "").strip()
        self.current_finalize_status = self.request.GET.get("finalize_status", "").strip()

    def apply_filters(self, queryset):
        self._load_filter_state()

        if self.current_run:
            queryset = queryset.filter(pipeline_run=self.current_run)

        if self.current_batch:
            queryset = queryset.filter(batch__pk=self.current_batch)

        if self.current_accession:
            queryset = queryset.filter(assembly_accession__icontains=self.current_accession)

        if self.current_method:
            queryset = queryset.filter(method=self.current_method)

        if self.current_residue:
            queryset = queryset.filter(repeat_residue=self.current_residue)

        if self.current_detect_status:
            queryset = queryset.filter(detect_status=self.current_detect_status)

        if self.current_finalize_status:
            queryset = queryset.filter(finalize_status=self.current_finalize_status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_run = getattr(self, "current_run", None)
        current_batch = getattr(self, "current_batch", "")

        filter_choices = AccessionCallCount.objects.all()
        batch_choices = AcquisitionBatch.objects.select_related("pipeline_run")
        if current_run:
            filter_choices = filter_choices.filter(pipeline_run=current_run)
            batch_choices = batch_choices.filter(pipeline_run=current_run)
        if current_batch:
            filter_choices = filter_choices.filter(batch__pk=current_batch)

        context["current_run"] = current_run
        context["current_run_id"] = current_run.run_id if current_run else ""
        context["selected_batch"] = _resolve_batch_filter(current_run, current_batch)
        context["current_batch"] = current_batch
        context["current_accession"] = getattr(self, "current_accession", "")
        context["current_method"] = getattr(self, "current_method", "")
        context["current_residue"] = getattr(self, "current_residue", "")
        context["current_detect_status"] = getattr(self, "current_detect_status", "")
        context["current_finalize_status"] = getattr(self, "current_finalize_status", "")
        context["run_choices"] = PipelineRun.objects.order_by("-imported_at", "run_id")
        context["batch_choices"] = batch_choices.order_by("pipeline_run__run_id", "batch_id")
        context["method_choices"] = filter_choices.order_by("method").values_list("method", flat=True).distinct()
        context["residue_choices"] = (
            filter_choices.exclude(repeat_residue="")
            .order_by("repeat_residue")
            .values_list("repeat_residue", flat=True)
            .distinct()
        )
        context["detect_status_choices"] = (
            filter_choices.exclude(detect_status="")
            .order_by("detect_status")
            .values_list("detect_status", flat=True)
            .distinct()
        )
        context["finalize_status_choices"] = (
            filter_choices.exclude(finalize_status="")
            .order_by("finalize_status")
            .values_list("finalize_status", flat=True)
            .distinct()
        )
        return context


class DownloadManifestEntryListView(VirtualScrollListView):
    model = DownloadManifestEntry
    template_name = "browser/downloadmanifest_list.html"
    context_object_name = "download_entries"
    virtual_scroll_row_template_name = "browser/includes/downloadmanifest_list_rows.html"
    virtual_scroll_colspan = 8
    search_fields = (
        "assembly_accession",
        "download_path",
        "rehydrated_path",
        "checksum",
        "notes",
    )
    ordering_map = {
        "accession": ("assembly_accession", "pipeline_run__run_id", "batch__batch_id"),
        "-accession": ("-assembly_accession", "pipeline_run__run_id", "batch__batch_id"),
        "batch": ("batch__batch_id", "assembly_accession"),
        "-batch": ("-batch__batch_id", "assembly_accession"),
        "run": ("pipeline_run__run_id", "batch__batch_id", "assembly_accession"),
        "-run": ("-pipeline_run__run_id", "batch__batch_id", "assembly_accession"),
        "download_status": ("download_status", "assembly_accession"),
        "-download_status": ("-download_status", "assembly_accession"),
        "package_mode": ("package_mode", "assembly_accession"),
        "-package_mode": ("-package_mode", "assembly_accession"),
        "file_size_bytes": ("file_size_bytes", "assembly_accession"),
        "-file_size_bytes": ("-file_size_bytes", "assembly_accession"),
        "checksum": ("checksum", "assembly_accession"),
        "-checksum": ("-checksum", "assembly_accession"),
        "paths": ("download_path", "rehydrated_path", "assembly_accession"),
        "-paths": ("-download_path", "-rehydrated_path", "assembly_accession"),
    }
    default_ordering = ("pipeline_run__run_id", "batch__batch_id", "assembly_accession")

    def get_base_queryset(self):
        return DownloadManifestEntry.objects.select_related("pipeline_run", "batch")

    def _load_filter_state(self):
        self.current_run = _resolve_current_run(self.request)
        self.current_batch = self.request.GET.get("batch", "").strip()
        self.current_accession = self.request.GET.get("accession", "").strip()
        self.current_download_status = self.request.GET.get("download_status", "").strip()
        self.current_package_mode = self.request.GET.get("package_mode", "").strip()

    def apply_filters(self, queryset):
        self._load_filter_state()

        if self.current_run:
            queryset = queryset.filter(pipeline_run=self.current_run)

        if self.current_batch:
            queryset = queryset.filter(batch__pk=self.current_batch)

        if self.current_accession:
            queryset = queryset.filter(assembly_accession__icontains=self.current_accession)

        if self.current_download_status:
            queryset = queryset.filter(download_status=self.current_download_status)

        if self.current_package_mode:
            queryset = queryset.filter(package_mode=self.current_package_mode)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_run = getattr(self, "current_run", None)
        current_batch = getattr(self, "current_batch", "")

        filter_choices = DownloadManifestEntry.objects.all()
        batch_choices = AcquisitionBatch.objects.select_related("pipeline_run")
        if current_run:
            filter_choices = filter_choices.filter(pipeline_run=current_run)
            batch_choices = batch_choices.filter(pipeline_run=current_run)
        if current_batch:
            filter_choices = filter_choices.filter(batch__pk=current_batch)

        context["current_run"] = current_run
        context["current_run_id"] = current_run.run_id if current_run else ""
        context["selected_batch"] = _resolve_batch_filter(current_run, current_batch)
        context["current_batch"] = current_batch
        context["current_accession"] = getattr(self, "current_accession", "")
        context["current_download_status"] = getattr(self, "current_download_status", "")
        context["current_package_mode"] = getattr(self, "current_package_mode", "")
        context["run_choices"] = PipelineRun.objects.order_by("-imported_at", "run_id")
        context["batch_choices"] = batch_choices.order_by("pipeline_run__run_id", "batch_id")
        context["download_status_choices"] = (
            filter_choices.exclude(download_status="")
            .order_by("download_status")
            .values_list("download_status", flat=True)
            .distinct()
        )
        context["package_mode_choices"] = (
            filter_choices.exclude(package_mode="")
            .order_by("package_mode")
            .values_list("package_mode", flat=True)
            .distinct()
        )
        return context


class TaxonListView(VirtualScrollListView):
    model = Taxon
    template_name = "browser/taxon_list.html"
    context_object_name = "taxa"
    virtual_scroll_row_template_name = "browser/includes/taxon_list_rows.html"
    virtual_scroll_colspan = 4
    search_fields = ("taxon_name",)
    ordering_map = {
        "taxon_name": ("taxon_name", "taxon_id"),
        "-taxon_name": ("-taxon_name", "taxon_id"),
        "taxon_id": ("taxon_id",),
        "-taxon_id": ("-taxon_id",),
        "rank": ("rank", "taxon_name"),
        "-rank": ("-rank", "taxon_name"),
        "parent": ("parent_taxon__taxon_name", "taxon_name", "taxon_id"),
        "-parent": ("-parent_taxon__taxon_name", "taxon_name", "taxon_id"),
    }
    default_ordering = ("taxon_name", "taxon_id")

    def get_base_queryset(self):
        return Taxon.objects.select_related("parent_taxon")

    def apply_search(self, queryset):
        query = self.get_search_query()
        if not query:
            return queryset
        search_filter = Q(taxon_name__icontains=query)
        if query.isdigit():
            search_filter |= Q(taxon_id=int(query))
        return queryset.filter(search_filter)

    def apply_filters(self, queryset):
        self.current_run = _resolve_current_run(self.request)
        self.branch_scope = _resolve_branch_scope(self.request)
        self.selected_branch_taxon = self.branch_scope["selected_branch_taxon"]
        self.current_rank = self.request.GET.get("rank", "").strip()
        self.current_mode = _resolve_browser_mode(self.request)

        if self.current_run:
            queryset = queryset.filter(pk__in=_run_taxon_ids(self.current_run))

        queryset = _apply_branch_scope_filter(queryset, branch_scope=self.branch_scope, field_name="pk")

        if self.current_rank:
            queryset = queryset.filter(rank=self.current_rank)

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_run = getattr(self, "current_run", None)
        selected_branch_taxon = getattr(self, "selected_branch_taxon", None)
        context["current_run"] = current_run
        context["current_run_id"] = current_run.run_id if current_run else ""
        context["current_mode"] = getattr(self, "current_mode", "run")
        context["run_choices"] = PipelineRun.objects.order_by("-imported_at", "run_id")
        context["current_rank"] = getattr(self, "current_rank", "")
        context["rank_choices"] = (
            Taxon.objects.exclude(rank="")
            .order_by("rank")
            .values_list("rank", flat=True)
            .distinct()
        )
        _update_branch_scope_context(context, getattr(self, "branch_scope", _resolve_branch_scope(self.request)))
        return context


class TaxonDetailView(DetailView):
    model = Taxon
    template_name = "browser/taxon_detail.html"
    context_object_name = "taxon"

    def get_queryset(self):
        return Taxon.objects.select_related("parent_taxon")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        taxon = self.object
        current_run = _resolve_current_run(self.request)
        current_mode = _resolve_browser_mode(self.request)
        branch_ids = _branch_taxon_ids(taxon)
        branch_genomes = Genome.objects.filter(taxon_id__in=branch_ids).select_related("pipeline_run", "taxon")
        branch_proteins = Protein.objects.filter(taxon_id__in=branch_ids)
        branch_repeat_calls = RepeatCall.objects.filter(taxon_id__in=branch_ids)

        if current_run:
            branch_genomes = branch_genomes.filter(pipeline_run=current_run)
            branch_proteins = branch_proteins.filter(pipeline_run=current_run)
            branch_repeat_calls = branch_repeat_calls.filter(pipeline_run=current_run)

        context["current_run"] = current_run
        context["current_run_id"] = current_run.run_id if current_run else ""
        context["current_mode"] = current_mode
        context["lineage"] = (
            TaxonClosure.objects.filter(descendant=taxon)
            .select_related("ancestor")
            .order_by("-depth", "ancestor__taxon_name")
        )
        context["descendant_count"] = TaxonClosure.objects.filter(ancestor=taxon, depth__gt=0).count()
        context["child_taxa"] = taxon.children.order_by("taxon_name")[:12]
        if current_mode == "merged":
            linked_accessions = list(
                accession_group_queryset(current_run=current_run, branch_taxon=taxon).order_by("accession")[:10]
            )
            context["branch_genomes_count"] = accession_group_queryset(
                current_run=current_run,
                branch_taxon=taxon,
            ).count()
            context["branch_proteins_count"] = len(
                merged_protein_groups(current_run=current_run, branch_taxon=taxon)
            )
            context["branch_repeat_calls_count"] = len(
                merged_repeat_call_groups(current_run=current_run, branch_taxon=taxon)
            )
            context["linked_accessions"] = linked_accessions
        else:
            context["branch_genomes_count"] = branch_genomes.count()
            context["branch_proteins_count"] = branch_proteins.count()
            context["branch_repeat_calls_count"] = branch_repeat_calls.count()
            context["linked_genomes"] = branch_genomes.order_by("accession", "pipeline_run__run_id")[:10]
        context["genome_branch_url"] = _url_with_query(
            reverse("browser:genome-list"),
            run=current_run.run_id if current_run else None,
            branch=taxon.pk,
            mode=current_mode,
        )
        context["protein_branch_url"] = _url_with_query(
            reverse("browser:protein-list"),
            run=current_run.run_id if current_run else None,
            branch=taxon.pk,
            mode=current_mode,
        )
        context["repeatcall_branch_url"] = _url_with_query(
            reverse("browser:repeatcall-list"),
            run=current_run.run_id if current_run else None,
            branch=taxon.pk,
            mode=current_mode,
        )
        context["accession_branch_url"] = _url_with_query(
            reverse("browser:accession-list"),
            run=current_run.run_id if current_run else None,
            branch=taxon.pk,
        )
        context["run_detail_url"] = reverse("browser:run-detail", args=[current_run.pk]) if current_run else ""
        return context


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
        selected_branch_taxon = getattr(self, "selected_branch_taxon", None)
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
        selected_branch_taxon = getattr(self, "selected_branch_taxon", None)
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


class AccessionsListView(VirtualScrollListView):
    template_name = "browser/accession_list.html"
    context_object_name = "accession_groups"
    virtual_scroll_row_template_name = "browser/includes/accession_list_rows.html"
    virtual_scroll_colspan = 7
    paginate_by = 20
    ordering_map = {
        "accession": ("accession",),
        "-accession": ("-accession",),
        "runs": ("-source_runs_count", "accession"),
        "-runs": ("source_runs_count", "accession"),
        "genomes": ("-source_genomes_count", "accession"),
        "-genomes": ("source_genomes_count", "accession"),
        "calls": ("-raw_repeat_calls_count", "accession"),
        "-calls": ("raw_repeat_calls_count", "accession"),
        "collapsed_calls": ("-collapsed_repeat_calls_count", "accession"),
        "-collapsed_calls": ("collapsed_repeat_calls_count", "accession"),
        "derived_proteins": ("-merged_repeat_bearing_proteins_count", "accession"),
        "-derived_proteins": ("merged_repeat_bearing_proteins_count", "accession"),
        "analyzed_proteins": ("-analyzed_protein_max", "-analyzed_protein_min", "accession"),
        "-analyzed_proteins": ("analyzed_protein_min", "analyzed_protein_max", "accession"),
    }
    default_ordering = ("accession",)

    def _get_analytics_summary(self):
        if not hasattr(self, "_analytics_summary"):
            self._analytics_summary = build_accession_analytics(
                current_run=getattr(self, "current_run", None),
                search_query=self.get_search_query(),
                branch_taxon=getattr(self, "selected_branch_taxon", None),
                branch_taxa_ids=getattr(self, "branch_scope", {}).get("branch_taxa_ids"),
            )
        return self._analytics_summary

    def get_search_query(self):
        return self.request.GET.get("q", "").strip()

    def _load_filter_state(self):
        self.current_run = _resolve_current_run(self.request)
        self.branch_scope = _resolve_branch_scope(self.request)
        self.selected_branch_taxon = self.branch_scope["selected_branch_taxon"]

    def get_ordering(self):
        requested_ordering = self.request.GET.get("order_by", "").strip()
        if requested_ordering in self.ordering_map:
            return self.ordering_map[requested_ordering]
        return self.default_ordering

    def get_queryset(self):
        self._load_filter_state()
        summary = self._get_analytics_summary()
        return _sort_dict_records(
            summary["accession_groups"],
            requested_ordering=self.request.GET.get("order_by", "").strip(),
            default_ordering="accession",
            key_map={
                "accession": lambda record: (record["accession"],),
                "runs": lambda record: (record["source_runs_count"], record["accession"]),
                "genomes": lambda record: (record["source_genomes_count"], record["accession"]),
                "calls": lambda record: (record["raw_repeat_calls_count"], record["accession"]),
                "collapsed_calls": lambda record: (record["collapsed_repeat_calls_count"], record["accession"]),
                "derived_proteins": lambda record: (
                    record["merged_repeat_bearing_proteins_count"],
                    record["accession"],
                ),
                "analyzed_proteins": lambda record: (
                    record["analyzed_protein_min"],
                    record["analyzed_protein_max"],
                    record["accession"],
                ),
            },
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        summary = self._get_analytics_summary()
        current_run = getattr(self, "current_run", None)
        context["summary"] = summary
        context["current_query"] = self.get_search_query()
        context["current_run"] = current_run
        context["current_run_id"] = current_run.run_id if current_run else ""
        context["run_choices"] = PipelineRun.objects.order_by("-imported_at", "run_id")
        context["current_order_by"] = self.request.GET.get("order_by", "").strip()
        context["ordering_options"] = [
            {"value": value, "label": _ordering_label(value)}
            for value in self.ordering_map.keys()
        ]
        _update_branch_scope_context(context, getattr(self, "branch_scope", _resolve_branch_scope(self.request)))
        page_query = self.request.GET.copy()
        page_query.pop("page", None)
        context["page_query"] = page_query.urlencode()
        return context


class AccessionDetailView(TemplateView):
    template_name = "browser/accession_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        accession = kwargs["accession"]

        try:
            summary = build_accession_summary(accession)
        except Genome.DoesNotExist as exc:
            raise Http404(str(exc)) from exc

        context.update(summary)
        context["genome_list_url"] = _url_with_query(reverse("browser:genome-list"), accession=accession)
        context["accession_list_url"] = reverse("browser:accession-list")
        context["protein_list_url"] = _url_with_query(reverse("browser:protein-list"), accession=accession)
        context["repeatcall_list_url"] = _url_with_query(reverse("browser:repeatcall-list"), accession=accession)
        context["merged_protein_list_url"] = _url_with_query(
            reverse("browser:protein-list"),
            accession=accession,
            mode="merged",
        )
        context["merged_repeatcall_list_url"] = _url_with_query(
            reverse("browser:repeatcall-list"),
            accession=accession,
            mode="merged",
        )
        return context


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
        "run": ("source_runs_count", "protein_name", "accession"),
        "-run": ("-source_runs_count", "protein_name", "accession"),
        "source_proteins": ("source_proteins_count", "protein_name", "accession"),
        "-source_proteins": ("-source_proteins_count", "protein_name", "accession"),
        "calls": ("collapsed_repeat_calls_count", "protein_name", "accession"),
        "-calls": ("-collapsed_repeat_calls_count", "protein_name", "accession"),
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
            records = merged_protein_groups(
                current_run=self.current_run,
                branch_taxon=self.selected_branch_taxon,
                branch_taxa_ids=self.branch_scope["branch_taxa_ids"],
                search_query=self.get_search_query(),
                gene_symbol=self.current_gene_symbol,
                accession_query=self.current_accession,
                genome_id=self.current_genome,
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
                default_ordering="protein_name",
                key_map={
                    "protein_name": lambda record: (record["protein_name"], record["accession"]),
                    "gene_symbol": lambda record: (record["gene_symbol_label"], record["protein_name"], record["accession"]),
                    "protein_length": lambda record: (record["protein_length"], record["protein_name"], record["accession"]),
                    "accession": lambda record: (record["accession"], record["protein_name"]),
                    "run": lambda record: (record["source_runs_count"], record["protein_name"], record["accession"]),
                    "source_proteins": lambda record: (
                        record["source_proteins_count"],
                        record["protein_name"],
                        record["accession"],
                    ),
                    "calls": lambda record: (
                        record["collapsed_repeat_calls_count"],
                        record["protein_name"],
                        record["accession"],
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
