import base64
import json

from django.db.models import Q


def _encode_cursor_token(values):
    payload = json.dumps(values, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_cursor_token(token: str):
    if not token:
        return None
    padding = "=" * (-len(token) % 4)
    try:
        payload = base64.urlsafe_b64decode(f"{token}{padding}".encode("ascii"))
        values = json.loads(payload.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    return values if isinstance(values, list) else None


def _reverse_ordering(ordering):
    reversed_ordering = []
    for field_name in ordering:
        if field_name.startswith("-"):
            reversed_ordering.append(field_name[1:])
        else:
            reversed_ordering.append(f"-{field_name}")
    return tuple(reversed_ordering)


def _cursor_values(instance, ordering):
    return [_cursor_field_value(instance, field_name) for field_name in ordering]


def _cursor_field_value(instance, field_name):
    current = instance
    for part in field_name.lstrip("-").split("__"):
        current = getattr(current, part)
    return current


def _cursor_filter_q(ordering, cursor_values, *, direction: str):
    if len(cursor_values) != len(ordering):
        return Q(pk__isnull=False)

    comparison = Q()
    equality_prefix = Q()
    for field_name, cursor_value in zip(ordering, cursor_values):
        descending = field_name.startswith("-")
        field_lookup = field_name.lstrip("-")
        if direction == "after":
            lookup = "lt" if descending else "gt"
        else:
            lookup = "gt" if descending else "lt"
        comparison |= equality_prefix & Q(**{f"{field_lookup}__{lookup}": cursor_value})
        equality_prefix &= Q(**{field_lookup: cursor_value})
    return comparison
