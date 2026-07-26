from __future__ import annotations

import importlib
import importlib.util
import json

import pytest

from rextio_benchmark.verification import GateError


def _output_api():
    assert importlib.util.find_spec("rextio_benchmark.output_table") is not None
    return importlib.import_module("rextio_benchmark.output_table")


def test_output_table_uses_domain_separated_exact_interning() -> None:
    api = _output_api()
    table = api.OutputTable()
    value = {"kind": "sequence", "values": [1, 2.0, True]}
    first = table.intern(value)
    second = table.intern({"values": [1, 2.0, True], "kind": "sequence"})
    assert first == second
    assert len(first) == 64
    assert table.values() == {first: value}
    plain = api.hashlib.sha256(api.canonical_output_bytes(value)).hexdigest()
    assert first != plain


def test_output_table_rejects_nonfinite_values_and_collisions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _output_api()
    with pytest.raises(GateError, match="finite"):
        api.OutputTable().intern({"value": float("nan")})
    table = api.OutputTable()
    monkeypatch.setattr(api, "output_digest", lambda value: "0" * 64)
    table.intern({"value": 1})
    with pytest.raises(GateError, match="collision"):
        table.intern({"value": 2})


def test_output_table_rejects_tamper_dangling_and_unreferenced_rows() -> None:
    api = _output_api()
    table = api.OutputTable()
    reference = table.intern({"value": 1.0})
    values = table.values()
    api.validate_output_table(values, {reference})

    tampered = {reference: {"value": 9.0}}
    with pytest.raises(GateError, match="digest"):
        api.validate_output_table(tampered, {reference})
    with pytest.raises(GateError, match="dangling"):
        api.validate_output_table(values, {"f" * 64})

    extra = api.OutputTable()
    used = extra.intern({"value": 1})
    extra.intern({"value": 2})
    with pytest.raises(GateError, match="unreferenced"):
        api.validate_output_table(extra.values(), {used})


def test_large_output_is_stored_once() -> None:
    api = _output_api()
    output = {"kind": "sequence", "values": [float(index) for index in range(10_000)]}
    table = api.OutputTable()
    references = [table.intern(output) for _ in range(51)]
    interned = json.dumps(
        {"output_table": table.values(), "references": references},
        separators=(",", ":"),
    )
    inline = json.dumps([output for _ in range(51)], separators=(",", ":"))
    assert len(table.values()) == 1
    assert len(interned) < len(inline) / 20
