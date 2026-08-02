# rextio-benchmark

<p align="center"><img src="./assets/readme/rextio-icon.png" width="104" alt="Rextio benchmark icon"></p>

<p align="center"><strong>An auditable CPU-first comparison of original Python source,<br>generated fallback, and verified Rextio native routes.</strong></p>

<p align="center">
  <a href="README.md">English</a> · <a href="README.ko.md">한국어</a> ·
  <a href="README.zh-hans.md">简体中文</a> · <a href="README.zh-hant.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a>
</p>

<p align="center">
  <img alt="GitHub repository version 0.1.1" src="https://img.shields.io/badge/repository-0.1.1-24292f">
  <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-blue"></a>
</p>

This repository is for developers and reviewers who want reproducible Rextio performance evidence rather than a headline alone. It covers **Rextio Core plus five first-party plugins**—NumPy, NetworkX, pandas, Torch, and TensorFlow—and keeps provenance, route proof, correctness checks, diagnostics, parity, and slowdowns visible.

```bash
scripts/run.sh quick
```

That command exercises the complete harness with short samples. Quick mode is deliberately **non-publishable**.

`rextio-benchmark` is distributed through GitHub only. Repository version **0.1.1** has no tag or PyPI package.

## Proof: the latest canonical CPU cohort

Three chronological runs on **Mac16,11 / Apple M4 Pro**, **2026-07-26**, CPython **3.11.9**, measured from clean commit [`92ef027`](https://github.com/rextio/rextio-benchmark/commit/92ef027cea25f9d6bf1d730de4c226d40016ba6e). The first report was selected chronologically, never by speedup.

| Domain | Three-run median speedup | Maximum deviation |
| --- | ---: | ---: |
| Core hybrid | 57.729× | 1.31% |
| NumPy mixed fusion | 2.523× | 3.88% |
| NetworkX Dijkstra | 3.679× | 1.09% |
| pandas `Series.map` | 66.143× | 0.92% |
| PyTorch CPU deep MLP | 1.017× | 0.41% |
| TensorFlow CPU eager chain | 1.040× | 0.38% |

All six predeclared headline rows passed the 10% stability gate. These are **workload-specific observations**, not library-wide speedup, release, support, or individual-change causal claims. Near 1× means parity.

The same canonical report deliberately retains unfavorable diagnostics: NumPy non-fused phase 1 **0.248×**, NumPy `dot` BLAS negative control **0.587×**, NumPy F64 direct-sink boundary **0.305×**, and TensorFlow small-batch pre/post **0.494×**. A ratio below 1× is valid evidence, not a failed report.

- [Canonical bundle](results/canonical/cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec/)
- [Chronological-first report](results/canonical/cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec/report.md)
- [Stability summary](results/canonical/cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec/stability.json)
- [Frozen publication policy](PUBLICATION.md)

## What is actually compared

Every timed lane starts a fresh process:

```text
python-source    → untouched module under cases/<case>/src
rextio-fallback  → generated package with REXTIO_NATIVE_MODE=fallback
rextio-native    → same package with native mode forced and threshold disabled
```

Before timing, the controller requires the exact `native-direct` or `native-plugin:*` route, `native_status=accepted`, a built native artifact, expected generated-source proof, and correct outputs. It rejects stale imports, hashes the source/build evidence, runs each command in a sanitized environment, resolves dependencies only from the profile's site-packages, requires artifacts under the exact case build root, captures full-output diagnostics, records effective framework thread counts, builds deterministic inputs outside timed regions, and records import/first-call time separately from steady-state samples.

The harness never invents or pre-populates numbers, drops an unfavorable result, uses a sliding window, or treats performance as a test threshold. Original source, generated fallback, and native outputs must agree under each case's declared exact or numeric comparison.

## First local run

Requirements:

- CPython **3.11 only** (`>=3.11,<3.12`)
- [uv](https://docs.astral.sh/uv/)
- stable Rust with `cargo` and `rustc`
- enough disk for isolated Torch and TensorFlow environments

Run the end-to-end quick path:

```bash
scripts/run.sh quick
```

Run one slower diagnostic publication attempt:

```bash
scripts/run.sh publish
```

Create a candidate canonical bundle only through the fixed three-attempt cohort path:

```bash
scripts/run.sh cohort
```

The wrapper exits non-zero when bootstrap, build, benchmark, schema, evidence, correctness, route, clean-commit, or mode-specific publication checks fail. A large speedup alone never authorizes copying a report into `results/canonical/`.

Individual stages remain available for diagnosis:

```bash
scripts/bootstrap.sh cpu
scripts/build.sh cpu
scripts/benchmark.sh cpu quick
scripts/verify.sh results/local/benchmark-quick-YYYYMMDDTHHMMSSZ.json
```

## Measured package provenance

The latest 0.1.1 cohort measured four exact **pre-release Git candidates at measurement time** and two released PyPI artifacts. Matching versions released later do not rewrite this historical evidence.

| Package | Measured status | Exact Git commit |
| --- | --- | --- |
| `rextio` | 0.1.7 candidate | `b8b8ed11f6b7b7aae4c7ae5205d88529608e8e97` |
| `rextio-numpy` | 0.1.3 candidate | `cf461e6775780a598517980c555a1aec079285d8` |
| `rextio-networkx` | 0.1.1 released PyPI | `ffc8681756d6f690ac090fe6b03f6ba220896ded` |
| `rextio-pandas` | 0.1.2 released PyPI | `930a4fbfbd084a9869dbbf521770e811ea3d6652` |
| `rextio-torch` | 0.1.3 candidate | `1e92b24b154c7266dc37d19533fc3e17a8b05f9a` |
| `rextio-tensorflow` | 0.1.3 candidate | `1fdb2e1cd91d058a056db76c2e0a15d52c855053` |

Exact source declarations live in [`profiles/next-candidate.toml`](profiles/next-candidate.toml). NetworkX and pandas commits identify their release tags; the other four rows are not later PyPI artifacts.

## Cases and interpretation

| Case | What it demonstrates | Qualification |
| --- | --- | --- |
| Core hybrid / executable | Scalar arithmetic and nested control flow; closed Rust process separately includes startup | Wrapper/process overhead remains visible. |
| NumPy fusion | `(left + right) * (left - right)` | Requires fusion rule and generated helper proof. |
| NumPy phase 1 / direct sink / `dot` | Non-fused branch, boundary allocation, and BLAS-owned negative control | Diagnostics only; phase 1 is never a fusion claim and no speedup is presumed. |
| NetworkX | Typed-adapter Dijkstra on a deterministic graph | Unsupported raw NetworkX spellings are not compiled. |
| pandas | Exact numeric/boolean `Series.map` UDF pipeline | A manually vectorized pandas/NumPy rewrite may be faster. |
| Torch CPU | Bounded float32 inference and small-batch pre/post | Inference only; no training or unsupported device/dtype. |
| TensorFlow CPU | Eager matmul/activation/classification and small-batch pre/post | No `tf.function`; no result is presumed. |

Each case is an independent Rextio project under [`cases/`](cases/). Core, NumPy, NetworkX, and pandas use the base profile; Torch and TensorFlow use isolated locked environments to prevent ABI/runtime contamination.

## Frozen history and publication controls

The released 0.1.0 Apple M4 Pro cohort remains byte-immutable at [`cohort-15fa…`](results/canonical/cohort-15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8/). It was measured from clean commit [`ff7f4fe`](https://github.com/rextio/rextio-benchmark/commit/ff7f4fea34199d850bed0446a8a223ef730ddf17) and published in evidence commit [`e62a3f8`](https://github.com/rextio/rextio-benchmark/commit/e62a3f8fb1637f52288873fb077ba4efba0ead59). Later candidate numbers do not replace it.

The first implementation mistakenly applied the 10% stability veto to every diagnostic. The retained NumPy BLAS negative control varied by about 23%, while all six pre-frozen headline rows passed. The policy was amended to match that predeclared scope; none of the original three reports was discarded, and no faster replacement window was chosen.

Canonical evidence directories are immutable. Verification binds measurement commit, exact case set, package provenance, policy identity, raw reports, evidence objects, rendered Markdown, and stability JSON by digest. Dirty or unrelated checkouts cannot publish. Read [PUBLICATION.md](PUBLICATION.md) before producing or interpreting canonical evidence.

## Reports and CUDA boundary

Local JSON and Markdown reports go to gitignored `results/local/`. Build failures remain explicit in `results/local/build-cpu.json`; benchmark failures remain per-case blockers. CI checks deterministic lint, schema, statistics, lanes, routes, and Markdown; it does not run long benchmarks or impose speed thresholds.

CUDA profiles are scaffolding for future NVIDIA Linux/WSL2 runs. CPU scripts never install or execute them, and this repository contains **no CUDA measurement**. macOS evidence cannot establish CUDA support. CUDA remains non-promoting and non-certifying; TensorFlow additionally makes no kernel-activity or runtime-transfer claim.

## Development

```bash
PYTHONPATH=src profiles/base/.venv/bin/ruff check src tests cases
PYTHONPATH=src profiles/base/.venv/bin/python -m pytest
```

- [Changelog](CHANGELOG.md)
- [Publication policy](PUBLICATION.md)
- [Security](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [License](LICENSE) — MIT
