from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from typing import Any


def _scalar(value: object) -> bool | int | float | str | None:
    if type(value) in {bool, int, float, str} or value is None:
        return value  # type: ignore[return-value]
    item = getattr(value, "item", None)
    if callable(item):
        converted = item()
        if type(converted) in {bool, int, float, str} or converted is None:
            return converted
    raise TypeError(f"unsupported canonical scalar {type(value).__name__}")


def sequence(
    *,
    kind: str,
    shape: Sequence[int],
    dtype: str,
    values: Iterable[object],
) -> dict[str, Any]:
    return {
        "kind": kind,
        "shape": [int(dimension) for dimension in shape],
        "dtype": dtype,
        "values": [_scalar(value) for value in values],
    }


def exact_sequence(
    *,
    kind: str,
    shape: Sequence[int],
    dtype: str,
    values: Iterable[object],
) -> dict[str, Any]:
    canonical = sequence(kind=kind, shape=shape, dtype=dtype, values=values)
    payload = json.dumps(
        canonical,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return {
        "kind": kind,
        "shape": canonical["shape"],
        "dtype": dtype,
        "count": len(canonical["values"]),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def node_float_mapping(value: dict[object, object]) -> dict[str, Any]:
    items = sorted((int(node), float(distance)) for node, distance in value.items())
    return {
        "kind": "node-float-map",
        "items": [[node, distance] for node, distance in items],
    }
