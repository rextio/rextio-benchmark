# Publication and stability policy

This policy freezes the initial CPU headline selection before any canonical
performance result exists. A result that fails this policy is retained as local
evidence but is not published as canonical.

> **Methodology amendment after the first cohort:** The initial implementation
> incorrectly applied the 10 percent stability veto to every diagnostic case.
> It rejected the retained BLAS-owned NumPy `dot` negative control after that
> nonheadline result varied by approximately 23 percent. The first three
> reports remain the fixed cohort: no run was discarded, no sliding window or
> fastest-result selection was introduced, and all six pre-frozen README rows
> satisfied the 10 percent rule. The gate now matches that pre-frozen scope.

## Frozen headline rows

The Core README table contains exactly these rows, in this order:

| Domain | Benchmark id |
| --- | --- |
| Core | `core-hybrid` |
| NumPy | `numpy-mixed-fusion` |
| NetworkX | `networkx-dijkstra` |
| pandas | `pandas-series-map` |
| PyTorch CPU | `torch-cpu-deep-mlp` |
| TensorFlow CPU | `tensorflow-cpu-eager-chain` |

The full canonical report must still retain every repository case for the
active complete-case set. `core-native-executable` is reported separately
because process startup is included. `numpy-blas-dot-negative-control` is
retained as the BLAS-owned negative control. `numpy-mixed-nonfused-phase1` is
retained as a diagnostic for the phase=1 non-fused branch and is **never** a
fusion claim and **never** appears in the six-row README headline block.
Neither diagnostic may be substituted into the headline table after results
are known. Neutral and slower headline rows remain in the table.

## Released 0.1.0 complete-case set (frozen historical)

The published Mac CPU cohort
`cohort-15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8`
remains byte-immutable under
`results/canonical/cohort-15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8/`.
Its complete case set is the released 0.1.0 set (without
`numpy-mixed-nonfused-phase1`). Verification of that cohort continues against
that frozen complete set so historical reports stay verifiable after later
diagnostic expansion. Do not rewrite, re-hash, or re-measure that directory.

## Candidate plugin 0.1.3 cohort (second frozen policy; measured)

A second cohort policy was frozen **before** any candidate three-run
measurement under policy id `candidate-plugin-0.1.3-pre-measurement` (that id
is the immutable policy name bound into reports; it is not rewritten after
measurement). The qualifying three-run candidate cohort has since been
measured and is published as a **measured candidate** under package
**0.1.1 (Unreleased)**. The released **0.1.0** cohort and figures remain
historical and are not replaced.

| Field | Value |
| --- | --- |
| Policy id | `candidate-plugin-0.1.3-pre-measurement` (frozen name) |
| Policy version | `1` (same schema; no report schema bump) |
| Status | measured candidate (qualified three-run cohort published) |
| Published cohort | `cohort-becd31f91c54dcf398f7b3c48abdbb353c16665cacf5d102af7a03072d2b170a` |
| Measurement commit | `afd73d76107f9b7f352c8f5bb8a0ed382051f8bc` |
| Selection | chronological-first, exactly three publish reports |
| Headline stability | 10% on the six frozen README rows only (**passed**) |
| Complete cases | released 0.1.0 set **plus** `numpy-mixed-nonfused-phase1` |
| `rextio-numpy` | version `0.1.3` from Git rev `7316c47393a86f1c701049b878d01e8d8f561cdb` |
| `rextio-tensorflow` | version `0.1.3` from Git rev `346ca58148ed2563d4c7547dd8443d60cd4f905b` |

These pins are **unreleased commit-pinned candidate builds**. They are **not**
PyPI `rextio-numpy` 0.1.3 or `rextio-tensorflow` 0.1.3 releases. All other
plugin, core, and framework versions remain on their existing released pins.

Headline proof before timing:

- `numpy-mixed-fusion` must declare and satisfy leaves-mode
  `rextio-numpy/elementwise-chain-fusion` and a generated `__rxtnp_echain_`
  helper/source presence.
- `tensorflow-cpu-eager-chain` must declare and satisfy
  `rextio-tensorflow/transpose-f32-cpu-2d` and generated
  `rextio_tensorflow_runtime::transpose(` source presence, using a non-square
  weight with default rank-2 transpose.
- `numpy-mixed-nonfused-phase1` must not be described as fusion.

### Measured candidate headline results (no cherry-picking)

Three-run medians and maximum relative deviations (all six rows within 10%):

| Domain | 3-run median | Max deviation |
| --- | ---: | ---: |
| Core hybrid | 57.392× | 0.46% |
| NumPy mixed fusion | 0.289× | 4.38% |
| NetworkX Dijkstra | 3.694× | 4.71% |
| pandas Series.map | 66.091× | 1.39% |
| PyTorch CPU deep MLP | 1.014× | 0.81% |
| TensorFlow CPU eager chain | 0.994× | 0.39% |

Chronological-first canonical report timings (selected first report):

| Domain | Source → native | Speedup |
| --- | ---: | ---: |
| Core hybrid | 7.989583 ms → 0.140795 ms | 57.392× |
| NumPy mixed fusion | 0.052636 ms → 0.174234 ms | 0.302× |
| NetworkX Dijkstra | 53.579948 ms → 13.893143 ms | 3.868× |
| pandas Series.map | 179.848385 ms → 2.790601 ms | 65.172× |
| PyTorch CPU deep MLP | 0.390064 ms → 0.384463 ms | 1.014× |
| TensorFlow CPU eager chain | 0.650397 ms → 0.653509 ms | 0.997× |

Published diagnostics from that first report: Core executable **16.658×**,
NumPy phase1 non-fused **0.514×** (not a fusion claim), NumPy `dot` negative
control **0.241×**. Bundle path:
`results/canonical/cohort-becd31f91c54dcf398f7b3c48abdbb353c16665cacf5d102af7a03072d2b170a/`.
Do not rewrite, re-hash, re-measure, rename, or delete that directory. Do not
replace the frozen released 0.1.0 figures with these candidate numbers.

## Qualifying cohort

A cohort is the first three chronological `publish` attempts from one clean
measurement commit on one unchanged host. Every attempt must:

1. pass `scripts/verify.sh` with `mode=publish` and `publishable=true`;
2. contain the complete case set for the active cohort policy with no blocker
   or ineligible case;
3. use identical schema, benchmark configuration, measurement commit, system
   identity, toolchain, package versions, optional candidate
   policy/package_provenance bindings, and all hashed evidence declarations;
   and
4. contain finite positive timing samples and verifier-recomputed statistics.

Candidate cohorts additionally require report-level `policy` with policy id
`candidate-plugin-0.1.3-pre-measurement` and `package_provenance` captured from
installed PEP 610 `direct_url.json`, cross-checked against the exact pins and
the hashed profile lock/manifest run-inputs. The stability summary persists
`policy_id` and `candidate_plugins` for those cohorts.

For every case, take the three reports' `paired.median_speedup` values and
report each deviation from the three-run median. The 10 percent publication
gate applies only to the six pre-frozen headline rows. Core executable, the
NumPy BLAS negative control, and the phase1 non-fused diagnostic remain fully
published diagnostics even when their `within_threshold` field is false.
Crossing 1× is allowed; stability does not mean that native must be faster.

If any of the first three attempts fails qualification, or a headline row
fails stability, publish no result from that cohort. Diagnose the cause, make
any required change in a new measurement commit, and begin a new three-attempt
cohort. Do not discard an early run and slide to a more favorable later window.

## Canonical selection and commit identities

The first chronological report in the first qualifying cohort is canonical;
it is never selected by speedup. Publish all three cohort reports or an
equivalent hash-bound stability summary alongside it.

Prefer `scripts/run.sh cohort`, which builds once and then performs exactly
three attempts before bundling. When running stages manually, run
`rextio_benchmark cohort` with exactly those three paths in chronological
order. It verifies the full cohort while the measurement worktree is clean,
then writes one `cohort-<sha256>` directory containing the selected report, all
three byte-exact raw reports, content-addressed evidence objects, and a
manifest-bound `stability.json`. It also writes `report.md`; both the manifest
and canonical JSON bind its repository-relative path and SHA-256, and
verification independently re-renders and byte-compares it.

The report records the clean **measurement commit** that produced it. Adding
the report to `results/canonical/` necessarily creates a later **evidence
publication commit**. Public links pin the report to that later commit while
preserving the measurement commit in the evidence. No report is rerun merely
to make those two commit identities equal.

Bundling may run at that clean descendant policy/evidence commit. The recorded
measurement commit must remain its ancestor; run-inputs are verified from that
commit's Git blobs. For canonical bundles, run-output roles are resolved from
content-addressed bundled objects even when mutable live ignored `.rextio`
paths exist and differ. Dirty or unrelated checkouts are rejected for new
publication; quality CI uses full-history checkout and re-verifies both the
frozen released 0.1.0 canonical report and the measured candidate plugin 0.1.3
canonical report. Candidate verification additionally re-runs
`generated_expectations` against the resolved bundled portable `check.json`
and generated Rust source (not live files). Those expectations are not applied
retroactively to the released 0.1.0 cohort.

Generate Core README blocks only from that verified canonical report with
`rextio_benchmark readme-blocks`. The generator fixes the six rows above,
retains ratios below 1×, emits identical numbers and commit-pinned links in
all five localized blocks, and labels `candidate@REV` / candidate caveats only
from verified bound report policy and package provenance (never from version
strings alone). It never invents numbers and never inserts diagnostic cases
into the headline table.
Normalized outputs are stored once per case in the report's content-addressed
`output_table`. Publication verification recomputes every table address,
rejects dangling or unreferenced entries, and independently applies the
manifest's tolerance to resolved source, fallback, and native values.
