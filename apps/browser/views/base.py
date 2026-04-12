from django.db.models import Q
from django.views.generic import ListView

from .formatting import _ordering_label


class BrowserListView(ListView):
    paginate_by = 20
    ordering_map = {}
    default_ordering = ()
    search_fields = ()

    def get_base_queryset(self):
        return super().get_queryset()

    def get_search_query(self):
        return self.request.GET.get("q", "").strip()

    def build_sort_links(self, ordering_map, current_order_by=""):
        sort_links = {}
        if not ordering_map:
            return sort_links

        query = self.request.GET.copy()
        query.pop("fragment", None)
        query.pop("page", None)
        query.pop("after", None)
        query.pop("before", None)

        for ordering_value in ordering_map.keys():
            base_key = ordering_value[1:] if ordering_value.startswith("-") else ordering_value
            if base_key in sort_links:
                continue

            if current_order_by == f"-{base_key}":
                state = "desc"
                next_order_by = base_key
                indicator = "v"
            elif current_order_by == base_key:
                state = "asc"
                next_order_by = ""
                indicator = "^"
            else:
                state = "none"
                next_order_by = f"-{base_key}"
                indicator = ""

            link_query = query.copy()
            if next_order_by:
                link_query["order_by"] = next_order_by
            else:
                link_query.pop("order_by", None)

            sort_links[base_key] = {
                "url": f"{self.request.path}?{link_query.urlencode()}" if link_query else self.request.path,
                "state": state,
                "active": state != "none",
                "indicator": indicator,
            }

        return sort_links

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
        queryset = self.get_base_queryset()
        queryset = self.apply_search(queryset)
        queryset = self.apply_filters(queryset)
        ordering = self.get_ordering()
        if ordering:
            queryset = queryset.order_by(*ordering)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_query"] = self.get_search_query()
        current_order_by = self.request.GET.get("order_by", "").strip()
        context["current_order_by"] = current_order_by
        context["ordering_options"] = [
            {"value": value, "label": _ordering_label(value)}
            for value in self.ordering_map.keys()
        ]
        context["sort_links"] = self.build_sort_links(self.ordering_map, current_order_by=current_order_by)
        page_query = self.request.GET.copy()
        page_query.pop("page", None)
        page_query.pop("after", None)
        page_query.pop("before", None)
        context["page_query"] = page_query.urlencode()
        return context
