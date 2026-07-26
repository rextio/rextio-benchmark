# Security policy

## Trust boundary

This repository installs Python packages, invokes Rextio and the Rust
toolchain, imports benchmark modules, and executes generated native artifacts.
Run it only on source and dependencies you trust, in an environment you
control. Benchmark isolation is an evidence boundary, not a hostile-code
sandbox.

Generated reports must not contain credentials, environment secrets, or
author-machine absolute paths. Before publishing evidence, inspect the
canonical JSON and Markdown as well as captured tool output.

## Reporting a vulnerability

Report sensitive vulnerabilities through GitHub private vulnerability
reporting:

<https://github.com/rextio/rextio-benchmark/security/advisories/new>

Do not open a public issue for an undisclosed vulnerability. Non-sensitive
hardening suggestions and reproducibility bugs may use ordinary GitHub issues.
There is no formal embargo or guaranteed response-time policy for this
alpha-stage project.
