def _mapping_items(mapping: dict[str, object], *, exclude_keys: set[str] | None = None):
    items = []
    excluded = exclude_keys or set()
    for key, value in mapping.items():
        if key in excluded or value in ("", None):
            continue
        items.append(
            {
                "key": key,
                "label": key.replace("_", " ").capitalize(),
                "value": value,
            }
        )
    return items


def _ordering_label(value: str) -> str:
    direction = "ascending"
    field_name = value
    if value.startswith("-"):
        direction = "descending"
        field_name = value[1:]
    return f"{field_name.replace('_', ' ').title()} ({direction})"


def _sort_dict_records(records, *, requested_ordering: str, default_ordering: str, key_map: dict):
    ordering_value = requested_ordering or default_ordering
    reverse = ordering_value.startswith("-")
    key_name = ordering_value[1:] if reverse else ordering_value
    key_func = key_map.get(key_name)
    if key_func is None:
        return records
    return sorted(records, key=key_func, reverse=reverse)


def _parse_positive_int(value: str):
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    if parsed < 0:
        return None
    return parsed


def _parse_float(value: str):
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None
