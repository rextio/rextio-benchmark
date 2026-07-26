# Canonical reports

This directory contains only cohorts that passed the publication policy for
their frozen headline scope. The first canonical Mac CPU cohort is
[`cohort-15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8`](cohort-15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8/).
That released **0.1.0** directory is byte-frozen and must not be rewritten.
Quick reports are never canonical.

A second **pre-measurement** candidate-plugin 0.1.3 cohort policy is defined in
[PUBLICATION.md](../../PUBLICATION.md) and `rextio_benchmark.cohort`. No
candidate three-run bundle is published until it is measured and verified.

Use `python -m rextio_benchmark bundle <publish-report>` at the report's clean
recorded run commit. Each bundle contains a canonical report, a role-keyed
manifest, and content-addressed bytes for every `run-output` evidence role.
