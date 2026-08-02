# rextio-benchmark

<p align="center"><img src="./assets/readme/rextio-icon.png" width="104" alt="Rextio benchmark 圖示"></p>
<p align="center"><strong>CPU 優先、可稽核地比較原始 Python 原始碼、<br>產生的 fallback 與已驗證的 Rextio native 路徑。</strong></p>

<p align="center"><a href="README.md">English</a> · <a href="README.ko.md">한국어</a> · <a href="README.zh-hans.md">简体中文</a> · <a href="README.zh-hant.md">繁體中文</a> · <a href="README.ja.md">日本語</a></p>
<p align="center"><img alt="GitHub 儲存庫版本 0.1.1" src="https://img.shields.io/badge/repository-0.1.1-24292f"> <a href="LICENSE"><img alt="MIT 授權" src="https://img.shields.io/badge/license-MIT-blue"></a></p>

本儲存庫面向需要可重現 Rextio 效能證據、而不只是一個醒目數字的開發者與審閱者。它涵蓋 **Rextio Core 與五個第一方 plugin**（NumPy、NetworkX、pandas、Torch、TensorFlow），並公開 provenance、route 證明、正確性檢查、診斷、持平與較慢結果。

```bash
scripts/run.sh quick
```

這個命令用短 sample 執行完整 harness。Quick mode 刻意設為**不可發布**。

`rextio-benchmark` 只透過 GitHub 散布。儲存庫版本 **0.1.1** 沒有 tag，也沒有 PyPI package。

## 證據：最新 canonical CPU cohort

在 **Mac16,11 / Apple M4 Pro**、**2026-07-26**、CPython **3.11.9** 上，從 clean commit [`92ef027`](https://github.com/rextio/rextio-benchmark/commit/92ef027cea25f9d6bf1d730de4c226d40016ba6e) 依時間連續執行三次。第一份報告依時間順序選擇，不依速度選擇。

| 領域 | 三次執行中位加速比 | 最大偏差 |
| --- | ---: | ---: |
| Core hybrid | 57.729× | 1.31% |
| NumPy mixed fusion | 2.523× | 3.88% |
| NetworkX Dijkstra | 3.679× | 1.09% |
| pandas `Series.map` | 66.143× | 0.92% |
| PyTorch CPU deep MLP | 1.017× | 0.41% |
| TensorFlow CPU eager chain | 1.040× | 0.38% |

預先宣告的六個 headline row 全部通過 10% 穩定性 gate。這些是**特定工作負載觀測值**，不是函式庫層級加速、發布、支援或單項變更因果 A/B 主張。接近 1× 代表持平。

同一 canonical 報告也保留不利診斷：NumPy non-fused phase 1 **0.248×**、NumPy `dot` BLAS negative control **0.587×**、NumPy F64 direct-sink boundary **0.305×**、TensorFlow small-batch pre/post **0.494×**。低於 1× 是有效證據，不是失敗報告。

- [Canonical bundle](results/canonical/cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec/)
- [依時間順序的第一份報告](results/canonical/cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec/report.md)
- [穩定性摘要](results/canonical/cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec/stability.json)
- [凍結的發布政策](PUBLICATION.md)

## 實際比較內容

每個計時 lane 都從新 process 開始：

```text
python-source    → cases/<case>/src 下未修改的 module
rextio-fallback  → 使用 REXTIO_NATIVE_MODE=fallback 的產生 package
rextio-native    → 強制 native mode 並停用 threshold 的同一 package
```

計時前，controller 要求精確的 `native-direct` 或 `native-plugin:*` route、`native_status=accepted`、已建置 native artifact、預期 generated-source 證明與正確輸出。它拒絕 stale import，對 source/build 證據做 hash，在清理過的環境中執行每個命令，且只從該 profile 的 site-packages 載入依賴。它還要求 artifact 位於該 case 的精確 build root，記錄 full-output diagnostics 與實際 framework thread count，在 timed region 外建立 deterministic input，並將 import/first-call 時間與 steady-state sample 分開記錄。

Harness 不會捏造或預填數字、丟棄不利結果、使用 sliding window，或把效能當成測試門檻。原始 source、generated fallback、native 輸出必須通過每個 case 宣告的精確或數值比較。

## 第一次本機執行

需求：

- 僅 CPython **3.11**（`>=3.11,<3.12`）
- [uv](https://docs.astral.sh/uv/)
- 包含 `cargo`、`rustc` 的 stable Rust
- 足夠容納隔離 Torch/TensorFlow 環境的磁碟空間

```bash
scripts/run.sh quick
```

執行一次較慢的診斷發布嘗試：

```bash
scripts/run.sh publish
```

只能透過固定三次嘗試的 cohort 路徑產生 candidate canonical bundle：

```bash
scripts/run.sh cohort
```

只要 bootstrap、build、benchmark、schema、evidence、correctness、route、clean-commit 或 mode 特定發布檢查失敗，wrapper 就會以非零狀態結束。只有很大的 speedup 絕不允許將報告複製到 `results/canonical/`。

診斷用獨立階段：

```bash
scripts/bootstrap.sh cpu
scripts/build.sh cpu
scripts/benchmark.sh cpu quick
scripts/verify.sh results/local/benchmark-quick-YYYYMMDDTHHMMSSZ.json
```

## 測量套件 provenance

最新 0.1.1 cohort 測量了測量當時四個精確的 **pre-release Git candidate** 與兩個已發布 PyPI artifact。日後發布相同版本號不會改寫這份歷史證據。

| Package | 測量狀態 | 精確 Git commit |
| --- | --- | --- |
| `rextio` | 0.1.7 candidate | `b8b8ed11f6b7b7aae4c7ae5205d88529608e8e97` |
| `rextio-numpy` | 0.1.3 candidate | `cf461e6775780a598517980c555a1aec079285d8` |
| `rextio-networkx` | 0.1.1 released PyPI | `ffc8681756d6f690ac090fe6b03f6ba220896ded` |
| `rextio-pandas` | 0.1.2 released PyPI | `930a4fbfbd084a9869dbbf521770e811ea3d6652` |
| `rextio-torch` | 0.1.3 candidate | `1e92b24b154c7266dc37d19533fc3e17a8b05f9a` |
| `rextio-tensorflow` | 0.1.3 candidate | `1fdb2e1cd91d058a056db76c2e0a15d52c855053` |

精確 source 宣告位於 [`profiles/next-candidate.toml`](profiles/next-candidate.toml)。NetworkX/pandas commit 識別 release tag；其餘四列不是後來發布的 PyPI artifact。

## Case 與解讀

| Case | 展示內容 | 限定 |
| --- | --- | --- |
| Core hybrid / executable | Scalar 算術、巢狀控制流程，以及獨立的封閉 Rust process | Wrapper/process 開銷保持可見。 |
| NumPy fusion | `(left + right) * (left - right)` | 需要 fusion rule 與 generated helper 證明。 |
| NumPy phase 1 / direct sink / `dot` | Non-fused 分支、邊界配置、BLAS negative control | 僅診斷；phase 1 絕非 fusion claim，也不預設 speedup。 |
| NetworkX | Deterministic graph 上的 typed-adapter Dijkstra | 不編譯不支援的 raw NetworkX 拼法。 |
| pandas | 精確 numeric/boolean `Series.map` UDF pipeline | 手動 vectorized rewrite 可能更快。 |
| Torch CPU | 有界 float32 inference 與 small-batch pre/post | 僅 inference；不含 training 或不支援的 device/dtype。 |
| TensorFlow CPU | Eager matmul/activation/classification 與 small-batch pre/post | 不使用 `tf.function`；不預設結果。 |

每個 case 都是 [`cases/`](cases/) 下的獨立 Rextio project。Core/NumPy/NetworkX/pandas 使用 base profile；Torch/TensorFlow 使用隔離 lock 環境，避免 ABI/runtime 相互污染。

## 凍結歷史與發布控制

已發布 0.1.0 Apple M4 Pro cohort 以 byte-immutable 形式保留在 [`cohort-15fa…`](results/canonical/cohort-15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8/)。它測自 clean commit [`ff7f4fe`](https://github.com/rextio/rextio-benchmark/commit/ff7f4fea34199d850bed0446a8a223ef730ddf17)，發布於 evidence commit [`e62a3f8`](https://github.com/rextio/rextio-benchmark/commit/e62a3f8fb1637f52288873fb077ba4efba0ead59)。後續 candidate 數字不會取代它。

最初實作錯誤地對所有診斷套用 10% 穩定性 veto。保留的 NumPy BLAS negative control 偏差約 23%，但預先凍結的六個 headline row 全部通過。政策已改為符合預先宣告範圍；原始三份報告一份也未丟棄，也未選擇更快的替代窗口。

Canonical evidence directory 不可變。驗證以 digest 綁定 measurement commit、精確 case set、package provenance、policy identity、raw report、evidence object、rendered Markdown 與 stability JSON。dirty 或無關 checkout 無法發布。產生或解讀 canonical evidence 前請閱讀 [PUBLICATION.md](PUBLICATION.md)。

## 報告與 CUDA 邊界

本機 JSON/Markdown 寫入 gitignored `results/local/`。Build 失敗明確留在 `results/local/build-cpu.json`，benchmark 失敗留作每 case blocker。CI 只檢查 deterministic lint、schema、statistics、lane、route 與 Markdown；不會執行長 benchmark，也不設定 speed threshold。

CUDA profile 只是未來 NVIDIA Linux/WSL2 執行的 scaffolding。CPU script 從不安裝或執行它們，本儲存庫**沒有 CUDA 測量**。macOS 證據無法證明 CUDA 支援。CUDA 仍是 non-promoting/non-certifying；TensorFlow 也不主張 kernel activity 或 runtime transfer。

## 開發

```bash
PYTHONPATH=src profiles/base/.venv/bin/ruff check src tests cases
PYTHONPATH=src profiles/base/.venv/bin/python -m pytest
```

- [變更記錄](CHANGELOG.md) · [發布政策](PUBLICATION.md) · [安全](SECURITY.md) · [貢獻](CONTRIBUTING.md) · [MIT 授權](LICENSE)
