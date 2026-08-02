# rextio-benchmark

<p align="center"><img src="./assets/readme/rextio-icon.png" width="104" alt="Rextio benchmark 图标"></p>
<p align="center"><strong>CPU 优先、可审计地比较原始 Python 源码、<br>生成的 fallback 与已验证的 Rextio native 路径。</strong></p>

<p align="center"><a href="README.md">English</a> · <a href="README.ko.md">한국어</a> · <a href="README.zh-hans.md">简体中文</a> · <a href="README.zh-hant.md">繁體中文</a> · <a href="README.ja.md">日本語</a></p>
<p align="center"><img alt="GitHub 仓库版本 0.1.1" src="https://img.shields.io/badge/repository-0.1.1-24292f"> <a href="LICENSE"><img alt="MIT 许可证" src="https://img.shields.io/badge/license-MIT-blue"></a></p>

本仓库面向需要可复现 Rextio 性能证据、而不只是一条醒目数字的开发者和审阅者。它覆盖 **Rextio Core 与五个第一方插件**（NumPy、NetworkX、pandas、Torch、TensorFlow），并公开 provenance、route 证明、正确性检查、诊断、持平与慢速结果。

```bash
scripts/run.sh quick
```

该命令用短样本运行完整 harness。Quick mode 被刻意设为**不可发布**。

`rextio-benchmark` 只通过 GitHub 分发。仓库版本 **0.1.1** 没有 tag，也没有 PyPI 包。

## 证据：最新 canonical CPU cohort

在 **Mac16,11 / Apple M4 Pro**、**2026-07-26**、CPython **3.11.9** 上，从 clean commit [`92ef027`](https://github.com/rextio/rextio-benchmark/commit/92ef027cea25f9d6bf1d730de4c226d40016ba6e) 连续运行三次。第一份报告按时间顺序选择，而不是按速度选择。

| 领域 | 三次运行中位加速比 | 最大偏差 |
| --- | ---: | ---: |
| Core hybrid | 57.729× | 1.31% |
| NumPy mixed fusion | 2.523× | 3.88% |
| NetworkX Dijkstra | 3.679× | 1.09% |
| pandas `Series.map` | 66.143× | 0.92% |
| PyTorch CPU deep MLP | 1.017× | 0.41% |
| TensorFlow CPU eager chain | 1.040× | 0.38% |

预先声明的六个 headline row 全部通过 10% 稳定性 gate。这些是**特定工作负载观测值**，不是库级加速、发布、支持或单项改动因果 A/B 声明。接近 1× 表示持平。

同一 canonical 报告也保留不利诊断：NumPy non-fused phase 1 **0.248×**、NumPy `dot` BLAS negative control **0.587×**、NumPy F64 direct-sink boundary **0.305×**、TensorFlow small-batch pre/post **0.494×**。低于 1× 是有效证据，不是失败报告。

- [Canonical bundle](results/canonical/cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec/)
- [按时间顺序的第一份报告](results/canonical/cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec/report.md)
- [稳定性摘要](results/canonical/cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec/stability.json)
- [冻结的发布政策](PUBLICATION.md)

## 实际比较内容

每个计时 lane 都从新进程开始：

```text
python-source    → cases/<case>/src 下未经修改的 module
rextio-fallback  → 使用 REXTIO_NATIVE_MODE=fallback 的生成 package
rextio-native    → 强制 native mode 并禁用 threshold 的同一 package
```

计时前，controller 要求精确的 `native-direct` 或 `native-plugin:*` route、`native_status=accepted`、已构建 native artifact、预期 generated-source 证明以及正确输出。它拒绝 stale import，对 source/build 证据做 hash，清理环境，在 timed region 外构造 deterministic input，并把 import/first-call 时间与 steady-state sample 分开记录。

Harness 不会编造或预填数字、丢弃不利结果、使用 sliding window，或把性能当作测试阈值。原始 source、generated fallback、native 输出必须通过每个 case 声明的精确或数值比较。

## 第一次本地运行

要求：

- 仅 CPython **3.11**（`>=3.11,<3.12`）
- [uv](https://docs.astral.sh/uv/)
- 带 `cargo`、`rustc` 的 stable Rust
- 足够容纳隔离 Torch/TensorFlow 环境的磁盘空间

```bash
scripts/run.sh quick
```

运行一次较慢的诊断发布尝试：

```bash
scripts/run.sh publish
```

只能通过固定三次尝试的 cohort 路径生成 candidate canonical bundle：

```bash
scripts/run.sh cohort
```

只要 bootstrap、build、benchmark、schema、evidence、correctness、route、clean-commit 或 mode 特定发布检查失败，wrapper 就会以非零状态退出。仅凭很大的 speedup 绝不允许把报告复制到 `results/canonical/`。

诊断用独立阶段：

```bash
scripts/bootstrap.sh cpu
scripts/build.sh cpu
scripts/benchmark.sh cpu quick
scripts/verify.sh results/local/benchmark-quick-YYYYMMDDTHHMMSSZ.json
```

## 测量包 provenance

最新 0.1.1 cohort 测量了测量当时四个精确的 **pre-release Git candidate** 和两个已发布 PyPI artifact。以后发布相同版本号不会改写这份历史证据。

| Package | 测量状态 | 精确 Git commit |
| --- | --- | --- |
| `rextio` | 0.1.7 candidate | `b8b8ed11f6b7b7aae4c7ae5205d88529608e8e97` |
| `rextio-numpy` | 0.1.3 candidate | `cf461e6775780a598517980c555a1aec079285d8` |
| `rextio-networkx` | 0.1.1 released PyPI | `ffc8681756d6f690ac090fe6b03f6ba220896ded` |
| `rextio-pandas` | 0.1.2 released PyPI | `930a4fbfbd084a9869dbbf521770e811ea3d6652` |
| `rextio-torch` | 0.1.3 candidate | `1e92b24b154c7266dc37d19533fc3e17a8b05f9a` |
| `rextio-tensorflow` | 0.1.3 candidate | `1fdb2e1cd91d058a056db76c2e0a15d52c855053` |

精确 source 声明位于 [`profiles/next-candidate.toml`](profiles/next-candidate.toml)。NetworkX/pandas commit 标识 release tag；其余四行不是后来发布的 PyPI artifact。

## Case 与解释

| Case | 展示内容 | 限定 |
| --- | --- | --- |
| Core hybrid / executable | 标量算术、嵌套控制流，以及单独的闭合 Rust 进程 | Wrapper/process 开销保持可见。 |
| NumPy fusion | `(left + right) * (left - right)` | 需要 fusion rule 与 generated helper 证明。 |
| NumPy phase 1 / direct sink / `dot` | Non-fused 分支、边界分配、BLAS negative control | 仅诊断；phase 1 绝非 fusion claim，也不预设 speedup。 |
| NetworkX | Deterministic graph 上的 typed-adapter Dijkstra | 不编译不受支持的 raw NetworkX 拼写。 |
| pandas | 精确 numeric/boolean `Series.map` UDF pipeline | 手工 vectorized rewrite 可能更快。 |
| Torch CPU | 有界 float32 inference 与 small-batch pre/post | 仅推理；不含训练或不支持的 device/dtype。 |
| TensorFlow CPU | Eager matmul/activation/classification 与 small-batch pre/post | 不用 `tf.function`；不预设结果。 |

每个 case 都是 [`cases/`](cases/) 下的独立 Rextio project。Core/NumPy/NetworkX/pandas 使用 base profile；Torch/TensorFlow 使用隔离锁定环境，避免 ABI/runtime 相互污染。

## 冻结历史与发布控制

已发布 0.1.0 Apple M4 Pro cohort 以 byte-immutable 形式保留在 [`cohort-15fa…`](results/canonical/cohort-15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8/)。它测自 clean commit [`ff7f4fe`](https://github.com/rextio/rextio-benchmark/commit/ff7f4fea34199d850bed0446a8a223ef730ddf17)，发布于 evidence commit [`e62a3f8`](https://github.com/rextio/rextio-benchmark/commit/e62a3f8fb1637f52288873fb077ba4efba0ead59)。后续 candidate 数字不会替代它。

最初实现错误地对所有诊断应用 10% 稳定性 veto。保留的 NumPy BLAS negative control 偏差约 23%，但预先冻结的六个 headline row 全部通过。政策已改为符合预声明范围；原始三份报告一份也未丢弃，也未选择更快的替代窗口。

Canonical evidence directory 不可变。验证以 digest 绑定 measurement commit、精确 case set、package provenance、policy identity、raw report、evidence object、rendered Markdown 和 stability JSON。dirty 或无关 checkout 不能发布。生成或解释 canonical evidence 前请阅读 [PUBLICATION.md](PUBLICATION.md)。

## 报告与 CUDA 边界

本地 JSON/Markdown 写入 gitignored `results/local/`。Build 失败明确留在 `results/local/build-cpu.json`，benchmark 失败留作每 case blocker。CI 只检查 deterministic lint、schema、statistics、lane、route 和 Markdown；不会运行长 benchmark，也不设置 speed threshold。

CUDA profile 只是未来 NVIDIA Linux/WSL2 运行的 scaffolding。CPU script 从不安装或执行它们，本仓库**没有 CUDA 测量**。macOS 证据无法证明 CUDA 支持。CUDA 仍是 non-promoting/non-certifying；TensorFlow 也不声称 kernel activity 或 runtime transfer。

## 开发

```bash
PYTHONPATH=src profiles/base/.venv/bin/ruff check src tests cases
PYTHONPATH=src profiles/base/.venv/bin/python -m pytest
```

- [更新日志](CHANGELOG.md) · [发布政策](PUBLICATION.md) · [安全](SECURITY.md) · [贡献](CONTRIBUTING.md) · [MIT 许可证](LICENSE)
