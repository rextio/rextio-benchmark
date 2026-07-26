# Canonical reports

This directory intentionally contains no measurements yet. A report belongs
here only after repeated `publish` runs pass every route, correctness,
provenance, schema, and stability gate. Quick reports are never canonical.

Use `python -m rextio_benchmark bundle <publish-report>` at the report's clean
recorded run commit. Each bundle contains a canonical report, a role-keyed
manifest, and content-addressed bytes for every `run-output` evidence role.
