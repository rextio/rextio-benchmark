# Rextio benchmark report

- Mode: `publish`
- Generated: `2026-07-26T20:25:48.681081+00:00`
- Publishable: `true`
- Host: `macOS-26.5.2-arm64-arm-64bit`

| Case | Source median | Native median | Median speedup | Status |
| --- | ---: | ---: | ---: | --- |
| core-hybrid | 7.988211 ms | 0.138802 ms | 57.729× | passed |
| core-native-executable | 45.805401 ms | 2.875729 ms | 15.977× | passed |
| networkx-dijkstra | 50.836724 ms | 13.651031 ms | 3.719× | passed |
| numpy-f64-1d-boundary-direct-sink | 0.000705 ms | 0.002318 ms | 0.305× | passed |
| numpy-mixed-fusion | 0.051241 ms | 0.019296 ms | 2.425× | passed |
| numpy-mixed-nonfused-phase1 | 0.043069 ms | 0.178912 ms | 0.248× | passed |
| numpy-blas-dot-negative-control | 0.161487 ms | 0.275881 ms | 0.587× | passed |
| pandas-series-map | 179.817448 ms | 2.700109 ms | 66.143× | passed |
| tensorflow-cpu-small-batch-prepost | 0.091674 ms | 0.186025 ms | 0.494× | passed |
| tensorflow-cpu-eager-chain | 0.648913 ms | 0.622690 ms | 1.040× | passed |
| torch-cpu-small-batch-prepost | 0.006521 ms | 0.005629 ms | 1.158× | passed |
| torch-cpu-deep-mlp | 0.391130 ms | 0.385014 ms | 1.018× | passed |

Build, import, and first-call timings are separate from steady-state samples.
The Core executable row includes process startup in every retained observation.
Slower and negative-control results are intentionally preserved.
