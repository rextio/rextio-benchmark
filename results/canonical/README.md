# Canonical reports

This directory contains only cohorts that passed the publication policy for
their frozen headline scope. The first canonical Mac CPU cohort is
[`cohort-15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8`](cohort-15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8/).
That released **0.1.0** directory is byte-frozen and must not be rewritten.
Quick reports are never canonical.

A second measured candidate-plugin 0.1.3 cohort remains byte-frozen at
[`cohort-becd31f91c54dcf398f7b3c48abdbb353c16665cacf5d102af7a03072d2b170a`](cohort-becd31f91c54dcf398f7b3c48abdbb353c16665cacf5d102af7a03072d2b170a/).
The later measured boundary/pre-post candidate cohort is byte-frozen at
[`cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec`](cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec/).
Both candidate bundles use unreleased exact Git pins and are evidence, not
release or support claims. Their six headline rows follow the same frozen
selection policy; boundary/pre-post diagnostics remain non-headline and
non-gating. See [PUBLICATION.md](../../PUBLICATION.md).

Use `python -m rextio_benchmark bundle <publish-report>` at the report's clean
recorded run commit. Each bundle contains a canonical report, a role-keyed
manifest, and content-addressed bytes for every `run-output` evidence role.
