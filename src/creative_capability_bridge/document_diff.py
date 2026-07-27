"""Semantic comparison of inspected creative documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .inspection import inspect_document


def compare_documents(
    before: Path,
    after: Path,
    *,
    before_executable: str | None = None,
    after_executable: str | None = None,
) -> dict[str, Any]:
    left = inspect_document(before, executable=before_executable)
    right = inspect_document(after, executable=after_executable)
    return compare_inspections(left, right)


def compare_inspections(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_objects = _index(left.get("objects", []))
    right_objects = _index(right.get("objects", []))
    added = [right_objects[key] for key in sorted(right_objects.keys() - left_objects.keys())]
    removed = [left_objects[key] for key in sorted(left_objects.keys() - right_objects.keys())]
    changed: list[dict[str, Any]] = []
    unchanged: list[str] = []
    for identifier in sorted(left_objects.keys() & right_objects.keys()):
        fields = _changed_fields(left_objects[identifier], right_objects[identifier])
        if fields:
            changed.append({"id": identifier, "fields": fields})
        else:
            unchanged.append(identifier)
    return {
        "before": left.get("path"),
        "after": right.get("path"),
        "formats": {"before": left.get("format"), "after": right.get("format")},
        "equivalent": not added and not removed and not changed,
        "counts": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "unchanged": len(unchanged),
        },
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": unchanged,
    }


def _index(objects: Any) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    if not isinstance(objects, list):
        return indexed
    for position, item in enumerate(objects, start=1):
        if not isinstance(item, dict):
            continue
        identifier = item.get("id")
        key = str(identifier) if identifier else f"<anonymous-{position}>"
        indexed[key] = item
    return indexed


def _changed_fields(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    ignored = {"modifiable"}
    fields: dict[str, Any] = {}
    for key in sorted((left.keys() | right.keys()) - ignored - {"id"}):
        if left.get(key) != right.get(key):
            fields[key] = {"before": left.get(key), "after": right.get(key)}
    return fields
