# Rextio benchmark report

- Mode: `publish`
- Generated: `2026-07-26T14:40:49.161970+00:00`
- Publishable: `true`
- Host: `macOS-26.5.2-arm64-arm-64bit`

| Case | Source median | Native median | Median speedup | Status |
| --- | ---: | ---: | ---: | --- |
| core-hybrid | 7.989583 ms | 0.140795 ms | 57.392× | passed |
| core-native-executable | 45.072820 ms | 2.708790 ms | 16.658× | passed |
| networkx-dijkstra | 53.579948 ms | 13.893143 ms | 3.868× | passed |
| numpy-mixed-fusion | 0.052636 ms | 0.174234 ms | 0.302× | passed |
| numpy-mixed-nonfused-phase1 | 0.046358 ms | 0.088960 ms | 0.514× | passed |
| numpy-blas-dot-negative-control | 0.172286 ms | 0.717296 ms | 0.241× | passed |
| pandas-series-map | 179.848385 ms | 2.790601 ms | 65.172× | passed |
| tensorflow-cpu-eager-chain | 0.650397 ms | 0.653509 ms | 0.997× | passed |
| torch-cpu-deep-mlp | 0.390064 ms | 0.384463 ms | 1.014× | passed |

Build, import, and first-call timings are separate from steady-state samples.
The Core executable row includes process startup in every retained observation.
Slower and negative-control results are intentionally preserved.
