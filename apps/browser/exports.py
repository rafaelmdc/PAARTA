from django.http import StreamingHttpResponse
from django.utils.http import content_disposition_header


TSV_CONTENT_TYPE = "text/tab-separated-values; charset=utf-8"


def clean_tsv_value(value) -> str:
    if value is None:
        text = ""
    elif isinstance(value, bool):
        text = "true" if value else "false"
    else:
        text = str(value)

    return text.replace("\t", " ").replace("\r", " ").replace("\n", " ")


def _format_tsv_row(values) -> str:
    return "\t".join(clean_tsv_value(value) for value in values) + "\n"


def iter_tsv_rows(headers, rows):
    headers = tuple(headers)
    expected_width = len(headers)

    yield _format_tsv_row(headers)

    for row in rows:
        row = tuple(row)
        if len(row) != expected_width:
            raise ValueError(
                f"TSV row has {len(row)} cells but expected {expected_width}."
            )
        yield _format_tsv_row(row)


def stream_tsv_response(filename: str, headers, rows) -> StreamingHttpResponse:
    response = StreamingHttpResponse(
        iter_tsv_rows(headers, rows),
        content_type=TSV_CONTENT_TYPE,
    )
    response["Content-Disposition"] = content_disposition_header(
        as_attachment=True,
        filename=filename,
    )
    return response
