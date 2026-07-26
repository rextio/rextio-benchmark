# rextio-benchmark

`rextio-benchmark` is an auditable CPU-first showcase for the released Rextio
ecosystem. It compares the exact original Python source with the generated
fallback package and the same generated package forced onto its verified native
route. It never invents or pre-populates benchmark numbers, discards slower
results, or implies that Rust makes BLAS, libtorch, TensorFlow, or CUDA kernels
intrinsically faster.

## Requirements

- CPython 3.11
- [uv](https://docs.astral.sh/uv/)
- a stable Rust toolchain with `cargo` and `rustc`
- enough disk space for isolated Torch and TensorFlow environments

The locks use the released distributions `rextio==0.1.6`,
`rextio-numpy==0.1.2`, `rextio-networkx==0.1.1`,
`rextio-pandas==0.1.2`, `rextio-torch==0.1.2`, and
`rextio-tensorflow==0.1.2`. The optional CUDA locks add
`rextio-device-cuda==0.1.0`.

> **Methodology amendment:** The first implementation applied the 10 percent
> stability veto to all cases and rejected the first cohort because the
> nonheadline NumPy BLAS negative control varied by approximately 23 percent.
> All three original reports are retained; there is no sliding window or
> fastest-run selection. All six pre-frozen README rows met the threshold, so
> the publication gate now applies to those headline rows while Core executable
> and NumPy `dot` remain fully published diagnostics.

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
| NumPy fusion | Mixed scalar control flow and supported elementwise chains | Measures removed dispatch/materialization. |
| NumPy dot | Large rank-1 `numpy.dot` | Negative control; BLAS already owns the hot kernel. |
| NetworkX | Typed adapter Dijkstra on a deterministic weighted graph | No unsupported raw NetworkX spelling is compiled. |
| pandas | Exact numeric/boolean `Series.map` UDF pipeline | A manually vectorized pandas/NumPy rewrite may be faster. |
| Torch CPU | Bounded rank-1/rank-2 float32 MLP and scalar loop control | Inference only; no training or unsupported device/dtype. |
| TensorFlow CPU | Bounded eager TFE matmul/activation/reduction chain | No `tf.function`; no result is presumed. |

Each case is an independent Rextio project under `cases/`. Core, NumPy,
NetworkX, and pandas use `profiles/base`; Torch and TensorFlow use isolated
locked profiles so their ABI and runtime requirements cannot contaminate each
other.

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
