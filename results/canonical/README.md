# Canonical reports

This directory contains only cohorts that passed the publication policy for
their frozen headline scope. The first canonical Mac CPU cohort is
[`cohort-15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8`](cohort-15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8/).
Quick reports are never canonical.

Use `python -m rextio_benchmark bundle <publish-report>` at the report's clean
recorded run commit. Each bundle contains a canonical report, a role-keyed
manifest, and content-addressed bytes for every `run-output` evidence role.
