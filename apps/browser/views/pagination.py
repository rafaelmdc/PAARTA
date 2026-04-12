from django.http import JsonResponse
from django.template.loader import render_to_string

from .base import BrowserListView
from .cursor import (
    _cursor_filter_q,
    _cursor_values,
    _decode_cursor_token,
    _encode_cursor_token,
    _reverse_ordering,
)


class CursorPaginator:
    def __init__(self, count: int):
        self.count = count
        self.num_pages = None


class CursorPage:
    cursor_pagination = True
    number = None

    def __init__(self, *, object_list, count: int, previous_query: str = "", next_query: str = ""):
        self.object_list = object_list
        self.paginator = CursorPaginator(count)
        self.previous_query = previous_query
        self.next_query = next_query

    def has_previous(self):
        return bool(self.previous_query)

    def has_next(self):
        return bool(self.next_query)

    def has_other_pages(self):
        return self.has_previous() or self.has_next()


class CursorPaginatedListView(BrowserListView):
    cursor_after_param = "after"
    cursor_before_param = "before"

    def use_cursor_pagination(self, queryset):
        return False

    def uses_fast_default_ordering(self):
        return tuple(self.get_ordering() or ()) == tuple(self.default_ordering or ())

    def get_cursor_ordering(self):
        ordering = tuple(self.get_ordering() or ())
        if not ordering:
            return ordering

        normalized_fields = {field_name.lstrip("-") for field_name in ordering}
        if "pk" not in normalized_fields and "id" not in normalized_fields:
            ordering = ordering + ("pk",)
        return ordering

    def paginate_queryset(self, queryset, page_size):
        if not self.use_cursor_pagination(queryset):
            return super().paginate_queryset(queryset, page_size)

        ordering = self.get_cursor_ordering()
        if not ordering:
            return super().paginate_queryset(queryset, page_size)

        after_token = self.request.GET.get(self.cursor_after_param, "").strip()
        before_token = self.request.GET.get(self.cursor_before_param, "").strip()
        cursor_token = after_token or before_token
        direction = "after" if after_token else "before" if before_token else ""
        cursor_values = _decode_cursor_token(cursor_token) if cursor_token else None
        if cursor_token and (cursor_values is None or len(cursor_values) != len(ordering)):
            direction = ""

        queryset = queryset.order_by(*ordering)
        total_count = queryset.count()
        if direction and cursor_values is not None:
            queryset = queryset.filter(_cursor_filter_q(ordering, cursor_values, direction=direction))

        query_limit = page_size + 1
        if direction == "before":
            rows = list(queryset.order_by(*_reverse_ordering(ordering))[:query_limit])
            has_next = bool(cursor_token)
            has_previous = len(rows) > page_size
            if has_previous:
                rows = rows[:page_size]
            rows.reverse()
        else:
            rows = list(queryset[:query_limit])
            has_previous = bool(cursor_token)
            has_next = len(rows) > page_size
            if has_next:
                rows = rows[:page_size]

        previous_query = ""
        next_query = ""
        if rows:
            if has_previous:
                previous_query = self._cursor_query_string("before", _encode_cursor_token(_cursor_values(rows[0], ordering)))
            if has_next:
                next_query = self._cursor_query_string("after", _encode_cursor_token(_cursor_values(rows[-1], ordering)))

        page = CursorPage(
            object_list=rows,
            count=total_count,
            previous_query=previous_query,
            next_query=next_query,
        )
        return page.paginator, page, rows, page.has_other_pages()

    def _cursor_query_string(self, direction: str, cursor_token: str):
        query = self.request.GET.copy()
        query.pop("fragment", None)
        query.pop("page", None)
        query.pop(self.cursor_after_param, None)
        query.pop(self.cursor_before_param, None)
        query[self.cursor_after_param if direction == "after" else self.cursor_before_param] = cursor_token
        return query.urlencode()


class VirtualScrollListView(CursorPaginatedListView):
    virtual_scroll_row_template_name = ""
    virtual_scroll_colspan = 1
    virtual_scroll_window_pages = 8

    def virtual_scroll_enabled(self):
        return True

    def get_virtual_scroll_colspan(self, context):
        return self.virtual_scroll_colspan

    def include_virtual_scroll_count(self, *, context=None, page_obj=None):
        return True

    def _virtual_scroll_base_query(self):
        query = self.request.GET.copy()
        query.pop("fragment", None)
        query.pop("page", None)
        query.pop(self.cursor_after_param, None)
        query.pop(self.cursor_before_param, None)
        return query

    def _page_query_string(self, page_number: int):
        query = self._virtual_scroll_base_query()
        query["page"] = page_number
        return query.urlencode()

    def get_virtual_scroll_queries(self, page_obj):
        if not page_obj:
            return "", ""

        previous_query = getattr(page_obj, "previous_query", "")
        next_query = getattr(page_obj, "next_query", "")
        if getattr(page_obj, "cursor_pagination", False):
            return previous_query, next_query

        if hasattr(page_obj, "has_previous") and page_obj.has_previous():
            previous_query = self._page_query_string(page_obj.previous_page_number())
        if hasattr(page_obj, "has_next") and page_obj.has_next():
            next_query = self._page_query_string(page_obj.next_page_number())
        return previous_query, next_query

    def is_virtual_scroll_fragment_request(self):
        return (
            self.request.GET.get("fragment", "").strip() == "virtual-scroll"
            and self.request.headers.get("x-requested-with") == "XMLHttpRequest"
        )

    def render_to_response(self, context, **response_kwargs):
        if self.is_virtual_scroll_fragment_request() and context.get("virtual_scroll_enabled"):
            return JsonResponse(self._virtual_scroll_payload(context))
        return super().render_to_response(context, **response_kwargs)

    def _virtual_scroll_payload(self, context):
        object_list = list(context[self.context_object_name])
        rows_context = context.copy()
        rows_context[self.context_object_name] = object_list
        rows_html = render_to_string(
            self.virtual_scroll_row_template_name,
            rows_context,
            request=self.request,
        )
        page_obj = context["page_obj"]
        previous_query, next_query = self.get_virtual_scroll_queries(page_obj)
        payload = {
            "rows_html": rows_html,
            "row_count": len(object_list),
            "next_query": next_query,
            "previous_query": previous_query,
        }
        if self.include_virtual_scroll_count(context=context, page_obj=page_obj):
            payload["count"] = page_obj.paginator.count
        return payload

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page_obj = context.get("page_obj")
        enabled = page_obj is not None and bool(self.virtual_scroll_row_template_name) and self.virtual_scroll_enabled()
        previous_query, next_query = self.get_virtual_scroll_queries(page_obj)
        context["virtual_scroll_enabled"] = enabled
        context["virtual_scroll_fragment_url"] = self.request.path
        context["virtual_scroll_previous_query"] = previous_query
        context["virtual_scroll_next_query"] = next_query
        context["virtual_scroll_total_rows"] = page_obj.paginator.count if page_obj else 0
        context["virtual_scroll_colspan"] = self.get_virtual_scroll_colspan(context)
        context["virtual_scroll_window_pages"] = self.virtual_scroll_window_pages
        return context
