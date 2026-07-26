# Contributing to rextio-benchmark

Thanks for helping improve the benchmark. Correctness, reproducibility, and
honest interpretation take priority over obtaining a larger speedup.

## Development setup

Install the locked CPU profiles and run the deterministic quality gates:

```bash
scripts/bootstrap.sh cpu
PYTHONPATH=src profiles/base/.venv/bin/ruff check src tests cases
PYTHONPATH=src profiles/base/.venv/bin/python -m pytest
```

Use `scripts/run.sh quick` for an end-to-end local smoke. Quick reports are
always non-publishable.

## Contribution rules

- Add or update deterministic tests for behavior changes.
- Keep every benchmark input outside the timed region and every comparison
  semantically equivalent.
- Preserve slower, neutral, failed, and negative-control results.
- Never weaken route, artifact, correctness, clean-commit, or verifier gates to
  make a case eligible.
- Do not add hand-written performance numbers to README files.
- Do not move local output into `results/canonical/` unless
  [PUBLICATION.md](PUBLICATION.md) is satisfied.
- Keep CUDA evidence separate from the initial CPU publication scope.

Use focused Conventional Commit subjects such as `fix:`, `test:`, `docs:`, or
`ci:`. Explain any measurement-contract change explicitly in the pull request.

Security-sensitive reports must follow [SECURITY.md](SECURITY.md), not a public
issue. Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
