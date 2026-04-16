from django.urls import reverse
from django.views.generic import TemplateView

from apps.browser.stats import (
    apply_stats_filter_context,
    build_filtered_repeat_call_queryset,
    build_stats_filter_state,
)
from apps.browser.stats.params import ALLOWED_STATS_RANKS

from ...metadata import resolve_browser_facets
from ...models import PipelineRun


class RepeatLengthExplorerView(TemplateView):
    template_name = "browser/repeat_length_explorer.html"

    def _get_filter_state(self):
        if not hasattr(self, "_filter_state"):
            self._filter_state = build_stats_filter_state(self.request)
        return self._filter_state

    def _get_matching_repeat_calls_count(self) -> int:
        if not hasattr(self, "_matching_repeat_calls_count"):
            self._matching_repeat_calls_count = build_filtered_repeat_call_queryset(self._get_filter_state()).count()
        return self._matching_repeat_calls_count

    def _get_facet_choices(self) -> dict[str, list[str]]:
        if not hasattr(self, "_facet_choices"):
            filter_state = self._get_filter_state()
            if filter_state.current_run is not None:
                self._facet_choices = resolve_browser_facets(pipeline_run=filter_state.current_run)
            else:
                self._facet_choices = resolve_browser_facets()
        return self._facet_choices

    def _scope_items(self) -> list[dict[str, str]]:
        filter_state = self._get_filter_state()
        length_range = "Any length"
        if filter_state.length_min is not None or filter_state.length_max is not None:
            length_range = f"{filter_state.length_min if filter_state.length_min is not None else 0} to {filter_state.length_max if filter_state.length_max is not None else 'any'}"

        return [
            {
                "label": "Display rank",
                "value": filter_state.rank,
            },
            {
                "label": "Target search",
                "value": filter_state.q or "Any gene, protein, or accession prefix",
            },
            {
                "label": "Method",
                "value": filter_state.method or "All methods",
            },
            {
                "label": "Residue",
                "value": filter_state.residue or "All residues",
            },
            {
                "label": "Length range",
                "value": length_range,
            },
            {
                "label": "Minimum observations",
                "value": str(filter_state.min_count),
            },
            {
                "label": "Visible taxa limit",
                "value": str(filter_state.top_n),
            },
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filter_state = self._get_filter_state()
        facet_choices = self._get_facet_choices()

        apply_stats_filter_context(context, filter_state)
        context["matching_repeat_calls_count"] = self._get_matching_repeat_calls_count()
        context["run_choices"] = PipelineRun.objects.order_by("-imported_at", "run_id")
        context["rank_choices"] = [
            {"value": rank, "label": rank}
            for rank in ALLOWED_STATS_RANKS
        ]
        context["method_choices"] = facet_choices["methods"]
        context["residue_choices"] = facet_choices["residues"]
        context["scope_items"] = self._scope_items()
        context["reset_url"] = reverse("browser:lengths")
        return context
