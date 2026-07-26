from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

from .verification import GateError

OUTPUT_DOMAIN = b"rextio-benchmark-normalized-output-v1\0"
OUTPUT_REF_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def canonical_output_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except ValueError as error:
        raise GateError("normalized output must contain only finite JSON values") from error
    except (TypeError, UnicodeEncodeError) as error:
        raise GateError("normalized output is not canonical JSON") from error


def output_digest(value: object) -> str:
    return hashlib.sha256(OUTPUT_DOMAIN + canonical_output_bytes(value)).hexdigest()


class OutputTable:
    def __init__(self) -> None:
        self._values: dict[str, Any] = {}
        self._payloads: dict[str, bytes] = {}

    def intern(self, value: object) -> str:
        payload = canonical_output_bytes(value)
        digest = output_digest(value)
        prior = self._payloads.get(digest)
        if prior is not None and prior != payload:
            raise GateError(f"normalized output digest collision: {digest}")
        if prior is None:
            self._payloads[digest] = payload
            self._values[digest] = deepcopy(value)
        return digest

    def resolve(self, reference: str) -> Any:
        try:
            return self._values[reference]
        except KeyError as error:
            raise GateError(f"dangling normalized output reference: {reference}") from error

    def values(self) -> dict[str, Any]:
        return {digest: deepcopy(self._values[digest]) for digest in sorted(self._values)}


def validate_output_table(
    table: dict[str, Any],
    referenced: set[str],
) -> dict[str, Any]:
    for declared, value in table.items():
        if not OUTPUT_REF_PATTERN.fullmatch(declared):
            raise GateError(f"invalid normalized output reference: {declared!r}")
        actual = output_digest(value)
        if actual != declared:
            raise GateError(f"normalized output digest differs: {declared}")
    for reference in referenced:
        if not isinstance(reference, str) or not OUTPUT_REF_PATTERN.fullmatch(reference):
            raise GateError(f"invalid normalized output reference: {reference!r}")
    dangling = referenced.difference(table)
    if dangling:
        raise GateError(f"dangling normalized output reference: {sorted(dangling)[0]}")
    unreferenced = set(table).difference(referenced)
    if unreferenced:
        raise GateError(f"unreferenced normalized output: {sorted(unreferenced)[0]}")
    return table
