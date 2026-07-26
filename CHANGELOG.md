# Changelog

All notable changes to `rextio-benchmark` are documented here following Keep a
Changelog and Semantic Versioning conventions.

## [0.1.1] — Unreleased

Pre-measurement candidate-cohort definition for the unreleased plugin 0.1.3
line. This cut is **not** a new published performance claim and does **not**
replace the released 0.1.0 Mac CPU cohort.

### Added

- Define a second frozen, pre-measurement **candidate plugin 0.1.3** cohort
  policy alongside the released 0.1.0 complete-case set.
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

### Changed

- Bump the harness package to **0.1.1** (Unreleased) while preserving the
  complete **0.1.0** release history and the byte-frozen canonical cohort
  `cohort-15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8`.
- Correct headline `numpy-mixed-fusion` to pass `phase=0` so the timed path is
  the fused expression `(left + right) * (left - right)`.
- README block generator and all five locales state candidate version and
  commit caveats when reports carry the candidate plugin pins.
- Historical canonical verification accepts the frozen 0.1.0 complete-case set
  so old reports remain verifiable after the diagnostic case is added.

### Non-claims

- No new three-run candidate cohort is measured or published in this cut.
- Existing published 0.1.0 figures remain historical; this work invents no
  replacement numbers.
- Phase-1 is never described as a fusion claim.
- Candidate Git pins are not PyPI `rextio-numpy` 0.1.3 or `rextio-tensorflow`
  0.1.3 releases.

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
