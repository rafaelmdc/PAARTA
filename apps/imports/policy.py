from __future__ import annotations

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone


class UploadPolicyError(Exception):
    pass


def check_active_upload_limit(user) -> None:
    """Reject when the user already has too many active uploads."""
    limit = getattr(settings, "HOMOREPEAT_UPLOAD_MAX_ACTIVE_PER_USER", 0)
    if not limit or not _is_identified(user):
        return
    from apps.imports.models import UploadedRun

    active_statuses = {
        UploadedRun.Status.RECEIVING,
        UploadedRun.Status.RECEIVED,
        UploadedRun.Status.EXTRACTING,
    }
    active_count = UploadedRun.objects.filter(
        created_by=user,
        status__in=active_statuses,
    ).count()
    if active_count >= limit:
        raise UploadPolicyError(
            f"You already have {active_count} active upload(s). "
            f"Maximum allowed is {limit}. Wait for existing uploads to complete."
        )


def check_daily_bytes_limit(user, new_bytes: int) -> None:
    """Reject when accepting this upload would exceed the user's daily byte quota."""
    limit = getattr(settings, "HOMOREPEAT_UPLOAD_MAX_DAILY_BYTES_PER_USER", 0)
    if not limit or not _is_identified(user):
        return
    from apps.imports.models import UploadedRun

    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    used = (
        UploadedRun.objects.filter(
            created_by=user,
            created_at__gte=today_start,
        ).aggregate(total=Sum("size_bytes"))["total"]
        or 0
    )
    if used + new_bytes > limit:
        raise UploadPolicyError(
            f"Daily upload quota exceeded: accepting this upload would use "
            f"{used + new_bytes:,} bytes today, exceeding the {limit:,}-byte limit."
        )


def check_zip_size_limit(user, zip_bytes: int) -> None:
    """Reject when this upload exceeds the per-user zip size cap."""
    limit = getattr(settings, "HOMOREPEAT_UPLOAD_MAX_ZIP_BYTES_PER_USER", 0)
    if not limit or not _is_identified(user):
        return
    if zip_bytes > limit:
        raise UploadPolicyError(
            f"Upload size {zip_bytes:,} bytes exceeds your per-upload limit of {limit:,} bytes."
        )


def _is_identified(user) -> bool:
    return (
        user is not None
        and getattr(user, "is_authenticated", False)
        and not getattr(user, "is_anonymous", True)
    )
