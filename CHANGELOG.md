# Changelog

All notable changes to `rextio-benchmark` are documented here following Keep a
Changelog and Semantic Versioning conventions.

## [0.1.1] — Unreleased

Measured publication of the unreleased plugin **0.1.3** candidate Mac CPU
cohort under package **0.1.1 (Unreleased)**. This cut does **not** replace the
released **0.1.0** complete-case cohort or its historical figures.
`rextio-numpy==0.1.3` and `rextio-tensorflow==0.1.3` remain **unreleased
commit-pinned candidate builds**, not PyPI 0.1.3 releases.

### Added

- Define a second frozen **candidate plugin 0.1.3** cohort policy alongside the
  released 0.1.0 complete-case set (policy id
  `candidate-plugin-0.1.3-pre-measurement`; immutable name bound into reports).
- Pin `rextio-numpy==0.1.3` and `rextio-tensorflow==0.1.3` from exact Git
  revisions (not PyPI 0.1.3 releases) in the affected uv profiles.
- Add diagnostic case `numpy-mixed-nonfused-phase1` (`phase=1`) for the
  non-fused `(left - right) / (right + 2.0)` branch. It appears only in the
  full report, never in the six-row README headline block.
- Add fail-closed generated-source / plugin-rule expectations so headline
  NumPy fusion and TensorFlow default rank-2 transpose are proven in
  `check.json` and generated Rust before measurement proceeds.
- Reshape the TensorFlow headline workload to exercise exact default rank-2
  `tf.transpose` on a non-square weight before the existing bounded loop and
  classification.
- CI push/PR triggers now include the `0.1.1` integration branch.
- Publish the measured three-run candidate cohort
  `cohort-becd31f91c54dcf398f7b3c48abdbb353c16665cacf5d102af7a03072d2b170a`
  (measurement commit `afd73d76107f9b7f352c8f5bb8a0ed382051f8bc`; NumPy rev
  `7316c47393a86f1c701049b878d01e8d8f561cdb`; TensorFlow rev
  `346ca58148ed2563d4c7547dd8443d60cd4f905b`).
- Add a separate, unmeasured diagnostic definition for the NumPy `F64_1D`
  borrowed-input/direct Python-owned-output boundary plus Torch and TensorFlow
  CPU batch-1 preprocessing/postprocessing-heavy scoring paths. All three are
  non-headline and use exact semantic output validation.
- Add fail-closed integration-target and provenance surfaces for Core 0.1.7,
  NumPy/Torch/TensorFlow 0.1.3. Core is pinned to
  `b8b8ed11f6b7b7aae4c7ae5205d88529608e8e97` and TensorFlow to
  `1fdb2e1cd91d058a056db76c2e0a15d52c855053`; NumPy and Torch remain explicit
  pending placeholders until their integration merge commits exist.

### Changed

- Bump the harness package to **0.1.1** (Unreleased) while preserving the
  complete **0.1.0** release history and the byte-frozen canonical cohort
  `cohort-15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8`.
- Correct headline `numpy-mixed-fusion` to pass `phase=0` so the timed path is
  the fused expression `(left + right) * (left - right)`.
- README block generator and all five locales state candidate version and
  commit caveats only from verified bound report policy/provenance (never from
  version strings alone).
- Historical canonical verification accepts the frozen 0.1.0 complete-case set
  so old reports remain verifiable after the diagnostic case is added.
- Canonical verification treats bundled run-output evidence as authoritative
  over live ignored `.rextio` paths; candidate reports bind policy id
  `candidate-plugin-0.1.3-pre-measurement` plus exact PEP 610 / lock pins;
  quality CI uses full-history checkout and verifies **both** the frozen
  released canonical report and the measured candidate canonical report;
  candidate verification re-runs generated expectations against bundled
  check/source evidence.
- Document measured-candidate status and the published candidate figures in
  README and PUBLICATION while retaining full 0.1.0 historical wording and
  numbers.
- Register the measured candidate cohort as a byte-frozen historical nine-case
  set before expanding the live manifests, so both published cohorts continue
  to verify without rewriting any evidence.

### Measured candidate results (no cherry-picking)

Three-run medians / maximum deviations (10% headline stability **passed**):
Core **57.392×** (0.46%), NumPy fusion **0.289×** (4.38%), NetworkX
**3.694×** (4.71%), pandas **66.091×** (1.39%), Torch **1.014×** (0.81%),
TensorFlow **0.994×** (0.39%).

Chronological-first canonical report: Core 7.989583 ms → 0.140795 ms
(57.392×), NumPy 0.052636 ms → 0.174234 ms (0.302×), NetworkX 53.579948 ms →
13.893143 ms (3.868×), pandas 179.848385 ms → 2.790601 ms (65.172×), Torch
0.390064 ms → 0.384463 ms (1.014×), TensorFlow 0.650397 ms → 0.653509 ms
(0.997×). Diagnostics: Core executable **16.658×**, NumPy phase1 **0.514×**
(not a fusion claim), NumPy `dot` negative control **0.241×**.

### Non-claims

- This is **not** a new PyPI release of `rextio-numpy` 0.1.3 or
  `rextio-tensorflow` 0.1.3; pins are exact unreleased Git revisions only.
- Existing published **0.1.0** figures remain historical and are not replaced
  by the candidate cohort.
- Phase-1 is never described as a fusion claim.
- Unfavorable and parity headline rows (NumPy fusion slowdown; Torch/TensorFlow
  near 1×) are retained deliberately; no sliding window or fastest-run
  selection.

## [0.1.0] — 2026-07-26

Initial public auditable CPU benchmark showcase.

- Locked profiles for Core, NumPy, NetworkX, pandas, Torch CPU, and TensorFlow
  CPU against the 2026-07-26 ecosystem release line (`rextio==0.1.6`,
  `rextio-numpy==0.1.2`, `rextio-networkx==0.1.1`, `rextio-pandas==0.1.2`,
  `rextio-torch==0.1.2`, `rextio-tensorflow==0.1.2`).
- Three-lane measurement contract (Python source / generated fallback /
  forced native) with fail-closed route, artifact, correctness, clean-commit,
  schema, and evidence-digest gates.
- Frozen six-row README headline scope and chronological-first three-run
  publication policy ([PUBLICATION.md](PUBLICATION.md)).
- Canonical Apple M4 Pro cohort
  `cohort-15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8`
  measured from clean commit `ff7f4fea`, published in evidence commit
  `e62a3f8`. Headline stability met the 10% gate; the NumPy BLAS negative
  control and Core executable remain published diagnostics.
- Localized Core README block generator for all five translations.
- Optional CUDA profile scaffolding without CPU-suite execution or CUDA
  support claims.
