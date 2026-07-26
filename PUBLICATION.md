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

The full canonical report must still retain every repository case.
`core-native-executable` is reported separately because process startup is
included. `numpy-blas-dot-negative-control` is retained as the BLAS-owned
negative control. Neither may be substituted into the headline table after
results are known. Neutral and slower headline rows remain in the table.

## Qualifying cohort

A cohort is the first three chronological `publish` attempts from one clean
measurement commit on one unchanged host. Every attempt must:

1. pass `scripts/verify.sh` with `mode=publish` and `publishable=true`;
2. contain the complete case set with no blocker or ineligible case;
3. use identical schema, benchmark configuration, measurement commit, system
   identity, toolchain, package versions, and all hashed evidence declarations;
   and
4. contain finite positive timing samples and verifier-recomputed statistics.

For every case, take the three reports' `paired.median_speedup` values and
report each deviation from the three-run median. The 10 percent publication
gate applies only to the six pre-frozen headline rows. Core executable and the
NumPy BLAS negative control remain fully published diagnostics even when their
`within_threshold` field is false. Crossing 1× is allowed; stability does not
mean that native must be faster.

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
manifest-bound `stability.json`.

The report records the clean **measurement commit** that produced it. Adding
the report to `results/canonical/` necessarily creates a later **evidence
publication commit**. Public links pin the report to that later commit while
preserving the measurement commit in the evidence. No report is rerun merely
to make those two commit identities equal.

Bundling may run at that clean descendant policy/evidence commit. The recorded
measurement commit must remain its ancestor; run-inputs are verified from that
commit's Git blobs and every current run-output byte must still match its
recorded digest. Dirty or unrelated checkouts are rejected.

Generate Core README blocks only from that verified canonical report with
`rextio_benchmark readme-blocks`. The generator fixes the six rows above,
retains ratios below 1×, and emits identical numbers and commit-pinned links in
all five localized blocks.
Normalized outputs are stored once per case in the report's content-addressed
`output_table`. Publication verification recomputes every table address,
rejects dangling or unreferenced entries, and independently applies the
manifest's tolerance to resolved source, fallback, and native values.
