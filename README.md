# rextio-benchmark

`rextio-benchmark` is an auditable CPU-first showcase for the Rextio ecosystem.
The suite covers **Rextio Core plus five first-party plugins** (NumPy,
NetworkX, pandas, Torch, and TensorFlow); each workload exercises its relevant
component. Package version **0.1.1 (Unreleased)** publishes the measured
unreleased plugin **0.1.3** candidate Mac CPU cohort while preserving the
complete **0.1.0** release history and its frozen published evidence. It
compares the exact original Python source with the generated fallback package
and the same generated package forced onto its verified native route. It never
invents or pre-populates benchmark numbers, discards slower results, or implies
that Rust makes BLAS, libtorch, TensorFlow, or CUDA kernels intrinsically
faster.

## Requirements

- CPython 3.11
- [uv](https://docs.astral.sh/uv/)
- a stable Rust toolchain with `cargo` and `rustc`
- enough disk space for isolated Torch and TensorFlow environments

The locks use **unreleased commit-pinned candidate** builds of Core 0.1.7,
NumPy 0.1.3, Torch 0.1.3, and TensorFlow 0.1.3 at the exact Git revisions
declared in `profiles/next-candidate.toml`. They are not corresponding PyPI
releases. NetworkX 0.1.1 and pandas 0.1.2 remain released pins; optional CUDA
locks also include released `rextio-device-cuda==0.1.0`. See
[CHANGELOG.md](CHANGELOG.md) and [PUBLICATION.md](PUBLICATION.md).

### Measured package provenance (0.1.1 suite)

The published boundary/pre-post Mac CPU cohort measures exactly these six
packages. NetworkX and pandas were installed as **released PyPI artifacts**;
their commit values identify the corresponding release tags. The other four
packages are **exact Git-pinned candidates** (not PyPI releases of those
versions).

| PyPI package | Measured version / status | Git commit (40-char) | Repository |
| --- | --- | --- | --- |
| `rextio` | 0.1.7 candidate | `b8b8ed11f6b7b7aae4c7ae5205d88529608e8e97` | https://github.com/rextio/rextio |
| `rextio-numpy` | 0.1.3 candidate | `cf461e6775780a598517980c555a1aec079285d8` | https://github.com/rextio/rextio-numpy |
| `rextio-networkx` | 0.1.1 released | `ffc8681756d6f690ac090fe6b03f6ba220896ded` | https://github.com/rextio/rextio-networkx |
| `rextio-pandas` | 0.1.2 released | `930a4fbfbd084a9869dbbf521770e811ea3d6652` | https://github.com/rextio/rextio-pandas |
| `rextio-torch` | 0.1.3 candidate | `1e92b24b154c7266dc37d19533fc3e17a8b05f9a` | https://github.com/rextio/rextio-torch |
| `rextio-tensorflow` | 0.1.3 candidate | `1fdb2e1cd91d058a056db76c2e0a15d52c855053` | https://github.com/rextio/rextio-tensorflow |

Canonical evidence directories under `results/canonical/` remain byte-immutable.

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
[`cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec`](results/canonical/cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec/)
on **Mac16,11 / Apple M4 Pro**, **2026-07-26**, CPython **3.11.9**, measured
from clean commit
[`92ef027cea25f9d6bf1d730de4c226d40016ba6e`](https://github.com/rextio/rextio-benchmark/commit/92ef027cea25f9d6bf1d730de4c226d40016ba6e).
The immutable policy id is `candidate-boundary-prepost-0.1.1` (a frozen
pre-measurement name); this is its subsequently measured candidate cohort.
Measured package provenance for Core plus the five first-party plugins is the
table above: four exact Git-pinned candidates and two released PyPI pins
(NetworkX 0.1.1, pandas 0.1.2) whose commits identify the release tags.

**Three-run medians** (headline rows; maximum relative deviation from the
three-run median; 10% stability gate):

| Domain | 3-run median speedup | Max deviation |
| --- | ---: | ---: |
| Core hybrid | 57.729× | 1.31% |
| NumPy mixed fusion | 2.523× | 3.88% |
| NetworkX Dijkstra | 3.679× | 1.09% |
| pandas Series.map | 66.143× | 0.92% |
| PyTorch CPU deep MLP | 1.017× | 0.41% |
| TensorFlow CPU eager chain | 1.040× | 0.38% |

All six headline rows passed the 10% stability veto.

**Chronological-first canonical report** (selected first of three; not chosen
by speedup):

| Domain | Python source | Rextio native | Speedup |
| --- | ---: | ---: | ---: |
| Core hybrid | 7.988211 ms | 0.138802 ms | 57.729× |
| NumPy mixed fusion | 0.051241 ms | 0.019296 ms | 2.425× |
| NetworkX Dijkstra | 50.836724 ms | 13.651031 ms | 3.719× |
| pandas Series.map | 179.817448 ms | 2.700109 ms | 66.143× |
| PyTorch CPU deep MLP | 0.391130 ms | 0.385014 ms | 1.018× |
| TensorFlow CPU eager chain | 0.648913 ms | 0.622690 ms | 1.040× |

**Published diagnostics** (full report only; never README headline substitutes
or stability gates), from the same chronological-first report: Core executable
**15.977×**, NumPy phase1 non-fused branch **0.248×** (not a fusion claim),
NumPy `dot` BLAS negative control **0.587×**, NumPy F64 direct-sink boundary
**0.305×**, Torch small-batch pre/post **1.158×** (three-run median
**1.156×**), and TensorFlow small-batch pre/post **0.494×** (three-run median
**0.495×**).

[Canonical report](results/canonical/cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec/report.md)
· [stability summary](results/canonical/cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec/stability.json)
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
The command verifies the hash-bound sibling `stability.json` before rendering:
it requires canonical cohort/policy identity, chronological index 0 of three
reports, exact case keys, a 10% threshold, and six passing headline gates.
Generated blocks therefore carry verified three-run medians rather than manual
stability claims.

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

The three new diagnostics belong to the separately measured
`candidate-boundary-prepost-0.1.1` cohort; they do not alter the six frozen
headline rows or become headline claims. Activation is deliberately fail-closed through
`profiles/next-candidate.toml`. Core 0.1.7 is pinned there to
`b8b8ed11f6b7b7aae4c7ae5205d88529608e8e97`, NumPy 0.1.3 to
`cf461e6775780a598517980c555a1aec079285d8`, and TensorFlow 0.1.3 to
`1fdb2e1cd91d058a056db76c2e0a15d52c855053`, and Torch 0.1.3 to
`1e92b24b154c7266dc37d19533fc3e17a8b05f9a`. Every revision is a full commit,
and the affected CPU profile manifests select those exact Git sources. The
policy was measured as the chronological-first three-run cohort linked above.

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
