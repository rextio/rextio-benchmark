# rextio-benchmark

`rextio-benchmark` is an auditable CPU-first showcase for the Rextio ecosystem.
Package version **0.1.1 (Unreleased)** publishes the measured unreleased
plugin **0.1.3** candidate Mac CPU cohort while preserving the complete
**0.1.0** release history and its frozen published evidence. It compares the
exact original Python source with the generated fallback package and the same
generated package forced onto its verified native route. It never invents or
pre-populates benchmark numbers, discards slower results, or implies that Rust
makes BLAS, libtorch, TensorFlow, or CUDA kernels intrinsically faster.

## Requirements

- CPython 3.11
- [uv](https://docs.astral.sh/uv/)
- a stable Rust toolchain with `cargo` and `rustc`
- enough disk space for isolated Torch and TensorFlow environments

The locks use the released distributions `rextio==0.1.6`,
`rextio-networkx==0.1.1`, `rextio-pandas==0.1.2`, and `rextio-torch==0.1.2`,
plus **unreleased commit-pinned candidate** builds
`rextio-numpy==0.1.3` at Git rev
`7316c47393a86f1c701049b878d01e8d8f561cdb` and
`rextio-tensorflow==0.1.3` at Git rev
`346ca58148ed2563d4c7547dd8443d60cd4f905b`. Those candidates are **not** PyPI
`rextio-numpy` 0.1.3 or `rextio-tensorflow` 0.1.3 releases. The optional CUDA
locks add released `rextio-device-cuda==0.1.0` and the same TensorFlow
candidate pin. See [CHANGELOG.md](CHANGELOG.md) and
[PUBLICATION.md](PUBLICATION.md).

> **Methodology amendment:** The first implementation applied the 10 percent
> stability veto to all cases and rejected the first cohort because the
> nonheadline NumPy BLAS negative control varied by approximately 23 percent.
> All three original reports are retained; there is no sliding window or
> fastest-run selection. All six pre-frozen README rows met the threshold, so
> the publication gate now applies to those headline rows while Core executable,
> NumPy `dot`, and the phase1 non-fused diagnostic remain fully published
> diagnostics. The released **0.1.0** canonical figures remain historical; the
> measured **0.1.3** candidate cohort below is an additional qualified
> publication under package **0.1.1 (Unreleased)**, not a replacement of 0.1.0.

## Verified CPU benchmark snapshots

These are workload-specific results, not library-wide performance claims.
Ratios below 1× mean Rextio was slower on that workload; values near 1× indicate
parity, not a material speedup. Neutral and slower headline rows are retained
with no cherry-picking.

### Unreleased plugin 0.1.3 candidate (measured)

Three-run chronological-first cohort
[`cohort-becd31f91c54dcf398f7b3c48abdbb353c16665cacf5d102af7a03072d2b170a`](results/canonical/cohort-becd31f91c54dcf398f7b3c48abdbb353c16665cacf5d102af7a03072d2b170a/)
on **Mac16,11 / Apple M4 Pro**, **2026-07-26**, CPython **3.11.9**, measured
from clean commit
[`afd73d76107f9b7f352c8f5bb8a0ed382051f8bc`](https://github.com/rextio/rextio-benchmark/commit/afd73d76107f9b7f352c8f5bb8a0ed382051f8bc).
Policy id remains `candidate-plugin-0.1.3-pre-measurement` (frozen name) with
measured-candidate publication status. Plugins:

- `rextio-numpy==0.1.3` candidate@`7316c47393a8` (Git rev
  `7316c47393a86f1c701049b878d01e8d8f561cdb`) — **not** a PyPI 0.1.3 release
- `rextio-tensorflow==0.1.3` candidate@`346ca58148ed` (Git rev
  `346ca58148ed2563d4c7547dd8443d60cd4f905b`) — **not** a PyPI 0.1.3 release
- released pins otherwise: `rextio==0.1.6`, `rextio-networkx==0.1.1`,
  `rextio-pandas==0.1.2`, `rextio-torch==0.1.2`

**Three-run medians** (headline rows; maximum relative deviation from the
three-run median; 10% stability gate):

| Domain | 3-run median speedup | Max deviation |
| --- | ---: | ---: |
| Core hybrid | 57.392× | 0.46% |
| NumPy mixed fusion | 0.289× | 4.38% |
| NetworkX Dijkstra | 3.694× | 4.71% |
| pandas Series.map | 66.091× | 1.39% |
| PyTorch CPU deep MLP | 1.014× | 0.81% |
| TensorFlow CPU eager chain | 0.994× | 0.39% |

All six headline rows passed the 10% stability veto.

**Chronological-first canonical report** (selected first of three; not chosen
by speedup):

| Domain | Python source | Rextio native | Speedup |
| --- | ---: | ---: | ---: |
| Core hybrid | 7.989583 ms | 0.140795 ms | 57.392× |
| NumPy mixed fusion | 0.052636 ms | 0.174234 ms | 0.302× |
| NetworkX Dijkstra | 53.579948 ms | 13.893143 ms | 3.868× |
| pandas Series.map | 179.848385 ms | 2.790601 ms | 65.172× |
| PyTorch CPU deep MLP | 0.390064 ms | 0.384463 ms | 1.014× |
| TensorFlow CPU eager chain | 0.650397 ms | 0.653509 ms | 0.997× |

**Published diagnostics** (full report only; never README headline substitutes),
from the same chronological-first report: Core executable **16.658×**, NumPy
phase1 non-fused branch **0.514×** (not a fusion claim), NumPy `dot` BLAS
negative control **0.241×**.

[Canonical report](results/canonical/cohort-becd31f91c54dcf398f7b3c48abdbb353c16665cacf5d102af7a03072d2b170a/report.md)
· [stability summary](results/canonical/cohort-becd31f91c54dcf398f7b3c48abdbb353c16665cacf5d102af7a03072d2b170a/stability.json)
· [PUBLICATION.md](PUBLICATION.md)

### Released 0.1.0 (historical, frozen)

The first public Mac CPU cohort remains byte-immutable at
[`cohort-15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8`](results/canonical/cohort-15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8/),
measured from clean commit
[`ff7f4fea34199d850bed0446a8a223ef730ddf17`](https://github.com/rextio/rextio-benchmark/commit/ff7f4fea34199d850bed0446a8a223ef730ddf17)
and published in evidence commit
[`e62a3f8fb1637f52288873fb077ba4efba0ead59`](https://github.com/rextio/rextio-benchmark/commit/e62a3f8fb1637f52288873fb077ba4efba0ead59).
Released pins only (`rextio-numpy==0.1.2`, `rextio-tensorflow==0.1.2`, and the
same other released package line). Headline stability met the 10% gate; the
NumPy BLAS negative control varied by about 23% and remains a published
non-headline diagnostic.

Chronological-first report (historical wording/figures retained):

| Domain | Python source | Rextio native | Speedup |
| --- | ---: | ---: | ---: |
| Core hybrid | 7.915661 ms | 0.138143 ms | 57.712× |
| NumPy mixed fusion | 0.041840 ms | 0.086150 ms | 0.485× |
| NetworkX Dijkstra | 50.581281 ms | 13.472185 ms | 3.751× |
| pandas Series.map | 179.454594 ms | 2.719183 ms | 66.002× |
| PyTorch CPU deep MLP | 0.388957 ms | 0.383640 ms | 1.014× |
| TensorFlow CPU eager chain | 0.727017 ms | 0.738452 ms | 0.984× |

Do not rewrite, re-hash, or re-measure that directory. Candidate figures above
do not replace these released 0.1.0 numbers.

## Run the CPU suite

One fail-closed entrypoint bootstraps every locked CPU profile, builds all
cases, runs the requested mode, and verifies the emitted report:

```bash
scripts/run.sh quick
```

Quick mode exercises the complete harness with short samples and is always
non-publishable. A single diagnostic publication attempt is deliberately
slower:

```bash
scripts/run.sh publish
```

For canonical evidence, use the cohort mode. It bootstraps and builds once,
runs and verifies exactly three chronological publish attempts without
rebuilding between them, applies the frozen stability rule, and writes the
canonical bundle:

```bash
scripts/run.sh cohort
```

The wrapper exits non-zero if any bootstrap, build, benchmark, schema,
evidence, or mode-specific publishability gate fails. The individual
`bootstrap.sh`, `build.sh`, `benchmark.sh`, and `verify.sh` stages remain
available for diagnosis:

```bash
scripts/bootstrap.sh cpu
scripts/build.sh cpu
scripts/benchmark.sh cpu quick
scripts/verify.sh results/local/benchmark-quick-YYYYMMDDTHHMMSSZ.json
```

Do not move a report into `results/canonical/` merely because it contains a
large speedup. Repeat runs must be stable and every route, correctness,
provenance, clean-commit, schema, and evidence-digest gate must pass. The
predeclared row set, repeat-run stability rule, and chronological canonical
selection are frozen in [PUBLICATION.md](PUBLICATION.md).

If diagnosing stages manually, bootstrap and build once, run
`scripts/benchmark.sh cpu publish` exactly three times, verify each result, and
then create the canonical cohort bundle:

```bash
PYTHONPATH=src profiles/base/.venv/bin/python -m rextio_benchmark cohort \
  results/local/benchmark-publish-FIRST.json \
  results/local/benchmark-publish-SECOND.json \
  results/local/benchmark-publish-THIRD.json
```

The command verifies all three before writing, rejects sliding windows and
unstable headline rows, reports deviation for every case, selects the first
report, copies all raw reports and `run-output` evidence into one
`cohort-<sha256>` directory, and writes a hash-bound stability summary plus a
human-readable `report.md`. Both the manifest and canonical JSON bind that
Markdown by repository-relative path and SHA-256, and verification
independently re-renders and byte-compares it. Bundling may run from a clean
descendant policy commit: inputs remain verified from the measurement commit
and current output bytes must retain their recorded digests. Dirty or
unrelated checkouts fail closed. After committing that bundle, render the five
localized Core README blocks with
`rextio_benchmark readme-blocks`; pass the canonical report, full
measurement/evidence commits, GitHub URL, and an output directory explicitly.

## Cases

| Case | Supported shape | Important interpretation |
| --- | --- | --- |
| Core hybrid | Scalar arithmetic and nested control-flow loops | Generated wrapper overhead remains visible. |
| Core executable | Closed direct-native call graph, Rust backend, `fallback=error` | Compares complete Python and Rust processes. |
| NumPy fusion (`numpy-mixed-fusion`) | `phase=0` path: `(left + right) * (left - right)` | Headline fusion claim; requires fusion rule + `__rxtnp_echain_` proof. |
| NumPy phase1 diagnostic | `phase=1` path: `(left - right) / (right + 2.0)` | Full-report only; **not** a fusion claim; never a README headline row. |
| NumPy F64_1D boundary diagnostic | Read-only rank-1 float64 input, one add, fresh direct-filled NumPy-owned output | Exact semantic validation; boundary/allocation diagnostic only; no speedup presumed. |
| NumPy dot | Large rank-1 `numpy.dot` | Negative control; BLAS already owns the hot kernel. |
| NetworkX | Typed adapter Dijkstra on a deterministic weighted graph | No unsupported raw NetworkX spelling is compiled. |
| pandas | Exact numeric/boolean `Series.map` UDF pipeline | A manually vectorized pandas/NumPy rewrite may be faster. |
| Torch CPU | Bounded rank-1/rank-2 float32 MLP and scalar loop control | Inference only; no training or unsupported device/dtype. |
| Torch CPU small-batch pre/post diagnostic | Batch 1, width 32, four scalar-controlled rounds, softmax and int64 argmax | Exact labels; diagnostic only; Python/tensor boundary overhead is intentionally large relative to the small kernels. |
| TensorFlow CPU | Default rank-2 transpose of non-square weight, then eager matmul/activation/classification | Requires transpose rule proof; no `tf.function`; no result is presumed. |
| TensorFlow CPU small-batch pre/post diagnostic | Batch 1, width 32, four scalar-controlled rounds, softmax and int64 argmax | Exact labels; eager diagnostic only; Python/tensor boundary overhead is intentionally large relative to the small kernels. |

Each case is an independent Rextio project under `cases/`. Core, NumPy,
NetworkX, and pandas use `profiles/base`; Torch and TensorFlow use isolated
locked profiles so their ABI and runtime requirements cannot contaminate each
other.

The three new diagnostics belong to the separate unmeasured policy
`candidate-boundary-prepost-0.1.1`; they do not alter the six frozen headline
rows. Activation is deliberately fail-closed through
`profiles/next-candidate.toml`. Core 0.1.7 is pinned there to
`b8b8ed11f6b7b7aae4c7ae5205d88529608e8e97` and TensorFlow 0.1.3 to
`1fdb2e1cd91d058a056db76c2e0a15d52c855053`; NumPy and Torch 0.1.3 remain
`PENDING_INTEGRATION_SHA` until their integration merges exist. Build and
benchmark commands refuse to start this policy until every revision is a full
commit and the affected CPU profile manifests select those exact Git sources.
No chronological-first run has been started or selected.

## Measurement contract

Every measured lane starts a fresh process and performs all retained samples
inside that process:

1. `python-source` imports the untouched module from `cases/<case>/src`.
2. `rextio-fallback` imports the generated package with
   `REXTIO_NATIVE_MODE=fallback`.
3. `rextio-native` imports that package with `REXTIO_NATIVE_MODE=native` and
   `REXTIO_DISABLE_BOUNDARY_FALLBACK=1`.

Before timing, the controller requires the manifest’s exact `native-direct` or
`native-plugin:*` route, `native_status=accepted`, and a built native artifact.
It rejects stale imports outside the current source/build tree and hashes the
artifact, `check.json`, `build.json`, case manifest, adapter, and untouched
workload. Inputs are deterministic and constructed outside timed regions.
Every worker starts from a sanitized environment whose only deliberate
`PYTHONPATH` entry is the benchmark harness. Before adding the workload import
root, the installed Core and enabled plugin origins must resolve inside the
selected profile's site-packages without importing them. The source lane keeps
that installed Core active; fallback/native lanes may activate only the
generated Core runtime under the exact case build root. Enabled plugins remain
profile-installed in every lane, and all active module files are recorded.

Run-input evidence also closes over the complete measurement harness, root
package and report schema, publication policy, and the bootstrap, build,
benchmark, verification, and end-to-end run scripts. The harness file set is
defined once by `MEASUREMENT_HARNESS_FILES` so correctness-defining modules
cannot silently fall outside the recorded commit identity.

Correctness uses deterministic full-output representations for floating-point
arrays and node-keyed mappings, and full-output SHA-256 digests for exact
integer and boolean arrays. Normalization and determinism checks occur outside
timed regions. Every configured thread variable and effective framework thread counts
are recorded.

Each case interns exact normalized JSON values in a domain-separated SHA-256
`output_table`. Observations and correctness evidence carry only table
references; the verifier recomputes every address before applying the
case-specific numeric tolerances. Paired records refer to their lane
observations instead of repeating output payloads.

Import and first-call time are recorded separately. Steady-state batches are
calibrated to a minimum duration. Publish mode uses warmups, counterbalanced
paired source/native order, raw samples, median, mean, MAD, p95, and a seeded
paired-bootstrap 95% interval. A ratio below 1× and a negative result are valid
evidence. Normal tests never assert a speed threshold.

The executable case has no generated-fallback timing lane: it additionally
compares the original Python command with the closed Rust process, so process
startup is intentionally part of each retained observation.

## Reports

Local output is written to the gitignored `results/local/` as versioned JSON
plus a Markdown rendering. `scripts/verify.sh` validates
`schema/benchmark-report-v1.schema.json`, semantic publication rules, current
case coverage, routes, raw samples, and evidence hashes. A dirty or unborn Git
state blocks publication but does not block an honest local quick report.
Reports record the Mac hardware model and Apple chip/CPU brand when available,
with portable architecture/processor fallbacks elsewhere. Recorded build
commands, tails, and Rextio report snapshots contain logical paths or redacted
placeholders rather than repository-root or home-directory absolute paths.

The repository never invents or pre-populates performance numbers. Build
failures remain explicit in `results/local/build-cpu.json`; benchmark failures
remain explicit per-case blockers in the report.

## CUDA boundary

`profiles/torch-cuda`, `profiles/tensorflow-cuda`, and the corresponding case
directories are scaffolding for a future NVIDIA Linux/WSL2 run. The CPU scripts
never install or execute them. macOS evidence cannot establish CUDA support.
CUDA remains non-promoting and non-certifying, and TensorFlow additionally
retains no kernel-activity or runtime-transfer claim.

## Development quality checks

```bash
PYTHONPATH=src profiles/base/.venv/bin/ruff check src tests cases
PYTHONPATH=src profiles/base/.venv/bin/python -m pytest
```

CI runs only deterministic lint, schema, statistics, lane, route-gate, and
Markdown tests. It never runs a long benchmark or treats performance as a
regression threshold.
