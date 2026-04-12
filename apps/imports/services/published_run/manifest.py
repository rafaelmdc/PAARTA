from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import (
    ACQUISITION_VALIDATION_COUNT_KEYS,
    ACQUISITION_VALIDATION_REQUIRED_KEYS,
    ImportContractError,
    MANIFEST_REQUIRED_KEYS,
    RequiredArtifactPaths,
)
from .iterators import _ensure_matching_batch_id, _parse_timestamp, _string_value


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ImportContractError(f"Malformed run manifest JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise ImportContractError(f"Run manifest must contain a top-level JSON object: {path}")

    missing = [key for key in MANIFEST_REQUIRED_KEYS if key not in payload]
    if missing:
        raise ImportContractError(f"Run manifest is missing required keys: {', '.join(missing)}")
    return payload


def _normalize_pipeline_run(
    manifest: dict[str, Any],
    artifact_paths: RequiredArtifactPaths,
) -> dict[str, Any]:
    return {
        "run_id": _require_manifest_value(manifest, "run_id"),
        "status": _require_manifest_value(manifest, "status"),
        "profile": _require_manifest_value(manifest, "profile"),
        "acquisition_publish_mode": _require_manifest_value(manifest, "acquisition_publish_mode"),
        "git_revision": _string_value(manifest.get("git_revision")),
        "started_at_utc": _parse_timestamp(manifest.get("started_at_utc"), "started_at_utc"),
        "finished_at_utc": _parse_timestamp(manifest.get("finished_at_utc"), "finished_at_utc"),
        "manifest_path": str(artifact_paths.manifest),
        "publish_root": str(artifact_paths.publish_root),
        "manifest_payload": manifest,
    }


def _ensure_raw_publish_mode(manifest: dict[str, Any]) -> None:
    acquisition_publish_mode = _require_manifest_value(manifest, "acquisition_publish_mode")
    if acquisition_publish_mode != "raw":
        raise ImportContractError(
            f"Published run uses acquisition_publish_mode={acquisition_publish_mode!r}; only 'raw' is supported."
        )


def _read_acquisition_validation_payload(path: Path, *, batch_id: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ImportContractError(f"Malformed acquisition validation JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise ImportContractError(f"Acquisition validation must contain a top-level JSON object: {path}")

    missing = [key for key in ACQUISITION_VALIDATION_REQUIRED_KEYS if key not in payload]
    if missing:
        raise ImportContractError(
            f"Acquisition validation is missing required keys: {', '.join(missing)}"
        )

    counts = payload.get("counts")
    if not isinstance(counts, dict):
        raise ImportContractError(f"Acquisition validation counts must be a JSON object: {path}")

    missing_count_keys = [key for key in ACQUISITION_VALIDATION_COUNT_KEYS if key not in counts]
    if missing_count_keys:
        raise ImportContractError(
            f"Acquisition validation counts are missing required keys: {', '.join(missing_count_keys)}"
        )

    payload_batch_id = _string_value(payload.get("batch_id"))
    if payload_batch_id:
        _ensure_matching_batch_id(path, expected_batch_id=batch_id, row_batch_id=payload_batch_id)
    return payload


def _require_manifest_value(manifest: dict[str, Any], key: str) -> str:
    value = _string_value(manifest.get(key))
    if not value:
        raise ImportContractError(f"Run manifest contains an empty required value for {key!r}")
    return value
