# Rextio benchmark report

- Mode: `publish`
- Generated: `2026-07-26T09:22:19.517029+00:00`
- Publishable: `true`
- Host: `macOS-26.5.2-arm64-arm-64bit`

| Case | Source median | Native median | Median speedup | Status |
| --- | ---: | ---: | ---: | --- |
| core-hybrid | 7.915661 ms | 0.138143 ms | 57.712× | passed |
| core-native-executable | 45.689338 ms | 2.830604 ms | 16.194× | passed |
| networkx-dijkstra | 50.581281 ms | 13.472185 ms | 3.751× | passed |
| numpy-mixed-fusion | 0.041840 ms | 0.086150 ms | 0.485× | passed |
| numpy-blas-dot-negative-control | 0.158589 ms | 0.715651 ms | 0.224× | passed |
| pandas-series-map | 179.454594 ms | 2.719183 ms | 66.002× | passed |
| tensorflow-cpu-eager-chain | 0.727017 ms | 0.738452 ms | 0.984× | passed |
| torch-cpu-deep-mlp | 0.388957 ms | 0.383640 ms | 1.014× | passed |

Build, import, and first-call timings are separate from steady-state samples.
The Core executable row includes process startup in every retained observation.
Slower and negative-control results are intentionally preserved.
