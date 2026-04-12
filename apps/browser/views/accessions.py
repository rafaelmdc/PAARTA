from django.http import Http404
from django.urls import reverse
from django.views.generic import TemplateView

from ..merged import build_accession_analytics, build_accession_summary
from ..models import Genome, PipelineRun
from .filters import _resolve_branch_scope, _resolve_current_run, _update_branch_scope_context
from .formatting import _ordering_label, _sort_dict_records
from .navigation import _url_with_query
from .pagination import VirtualScrollListView


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
