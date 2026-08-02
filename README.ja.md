# rextio-benchmark

<p align="center"><img src="./assets/readme/rextio-icon.png" width="104" alt="Rextio benchmark アイコン"></p>
<p align="center"><strong>元の Python ソース、生成 fallback、検証済み Rextio native 経路を<br>監査可能な形で比較する CPU-first ベンチマークです。</strong></p>

<p align="center"><a href="README.md">English</a> · <a href="README.ko.md">한국어</a> · <a href="README.zh-hans.md">简体中文</a> · <a href="README.zh-hant.md">繁體中文</a> · <a href="README.ja.md">日本語</a></p>
<p align="center"><img alt="GitHub リポジトリバージョン 0.1.1" src="https://img.shields.io/badge/repository-0.1.1-24292f"> <a href="LICENSE"><img alt="MIT ライセンス" src="https://img.shields.io/badge/license-MIT-blue"></a></p>

このリポジトリは、見出しの数字だけでなく再現可能な Rextio 性能証拠を求める開発者・レビュー担当者向けです。**Rextio Core と 5 つの first-party plugin**（NumPy、NetworkX、pandas、Torch、TensorFlow）を対象に、provenance、route 証明、正しさの検査、診断、同等・低速結果を公開します。

```bash
scripts/run.sh quick
```

短い sample で harness 全体を実行します。Quick mode は意図的に**公開不可**です。

`rextio-benchmark` の配布経路は GitHub のみです。リポジトリバージョン **0.1.1** に tag や PyPI package はありません。

## 証拠：最新 canonical CPU cohort

**Mac16,11 / Apple M4 Pro**、**2026-07-26**、CPython **3.11.9** 上で、clean commit [`92ef027`](https://github.com/rextio/rextio-benchmark/commit/92ef027cea25f9d6bf1d730de4c226d40016ba6e) から時系列で 3 回実行しました。最初の report は速度ではなく時系列で選びました。

| Domain | 3 回実行の中央高速化率 | 最大偏差 |
| --- | ---: | ---: |
| Core hybrid | 57.729× | 1.31% |
| NumPy mixed fusion | 2.523× | 3.88% |
| NetworkX Dijkstra | 3.679× | 1.09% |
| pandas `Series.map` | 66.143× | 0.92% |
| PyTorch CPU deep MLP | 1.017× | 0.41% |
| TensorFlow CPU eager chain | 1.040× | 0.38% |

事前宣言した 6 つの headline row はすべて 10% stability gate を通過しました。これは**特定ワークロードの観測**であり、ライブラリ全体の高速化、release/support、個別変更の因果的 A/B 主張ではありません。1× 付近は同等です。

同じ canonical report は不利な診断も保持します。NumPy non-fused phase 1 **0.248×**、NumPy `dot` BLAS negative control **0.587×**、NumPy F64 direct-sink boundary **0.305×**、TensorFlow small-batch pre/post **0.494×**。1× 未満も有効な証拠であり、report の失敗ではありません。

- [Canonical bundle](results/canonical/cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec/)
- [時系列で最初の report](results/canonical/cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec/report.md)
- [Stability summary](results/canonical/cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec/stability.json)
- [凍結された公開ポリシー](PUBLICATION.md)

## 実際の比較対象

各 timing lane は新しい process で始まります。

```text
python-source    → cases/<case>/src の未変更 module
rextio-fallback  → REXTIO_NATIVE_MODE=fallback の生成 package
rextio-native    → native mode を強制し threshold を無効にした同一 package
```

計測前に controller は正確な `native-direct` または `native-plugin:*` route、`native_status=accepted`、build 済み native artifact、期待する generated-source 証拠、正しい出力を要求します。stale import を拒否し、source/build 証拠を hash、環境を sanitize し、deterministic input を timed region 外で構築し、import/first-call 時間を steady-state sample と分けて記録します。

Harness は数値を捏造・事前投入せず、不利な結果を捨てず、sliding window を使わず、性能を test threshold にしません。元の source、generated fallback、native 出力は各 case の exact/numeric 比較を通過する必要があります。

## 最初のローカル実行

要件：

- CPython **3.11 のみ**（`>=3.11,<3.12`）
- [uv](https://docs.astral.sh/uv/)
- `cargo` と `rustc` を含む stable Rust
- 分離した Torch/TensorFlow 環境に十分な disk

```bash
scripts/run.sh quick
```

遅めの診断公開試行を 1 回実行：

```bash
scripts/run.sh publish
```

candidate canonical bundle は固定 3 回試行の cohort 経路だけで作成します。

```bash
scripts/run.sh cohort
```

bootstrap、build、benchmark、schema、evidence、correctness、route、clean-commit、mode 固有の公開検査のいずれかが失敗すると wrapper は非ゼロ終了します。大きな speedup だけでは `results/canonical/` へ report をコピーできません。

診断用の個別 stage：

```bash
scripts/bootstrap.sh cpu
scripts/build.sh cpu
scripts/benchmark.sh cpu quick
scripts/verify.sh results/local/benchmark-quick-YYYYMMDDTHHMMSSZ.json
```

## 計測 package provenance

最新 0.1.1 cohort は、計測時点の正確な **pre-release Git candidate 4 件**と公開済み PyPI artifact 2 件を測定しました。後から同じ version が公開されてもこの歴史的証拠は書き換わりません。

| Package | 計測時 status | 正確な Git commit |
| --- | --- | --- |
| `rextio` | 0.1.7 candidate | `b8b8ed11f6b7b7aae4c7ae5205d88529608e8e97` |
| `rextio-numpy` | 0.1.3 candidate | `cf461e6775780a598517980c555a1aec079285d8` |
| `rextio-networkx` | 0.1.1 released PyPI | `ffc8681756d6f690ac090fe6b03f6ba220896ded` |
| `rextio-pandas` | 0.1.2 released PyPI | `930a4fbfbd084a9869dbbf521770e811ea3d6652` |
| `rextio-torch` | 0.1.3 candidate | `1e92b24b154c7266dc37d19533fc3e17a8b05f9a` |
| `rextio-tensorflow` | 0.1.3 candidate | `1fdb2e1cd91d058a056db76c2e0a15d52c855053` |

正確な source 宣言は [`profiles/next-candidate.toml`](profiles/next-candidate.toml) にあります。NetworkX/pandas commit は release tag を示し、他の 4 行は後の PyPI artifact ではありません。

## Case と解釈

| Case | 示す内容 | 制約 |
| --- | --- | --- |
| Core hybrid / executable | Scalar 算術・ネスト制御フロー、別の閉じた Rust process | Wrapper/process overhead を含めます。 |
| NumPy fusion | `(left + right) * (left - right)` | Fusion rule と generated helper 証拠が必要です。 |
| NumPy phase 1 / direct sink / `dot` | Non-fused branch、boundary allocation、BLAS negative control | 診断専用。phase 1 は fusion claim ではなく、speedup を仮定しません。 |
| NetworkX | Deterministic graph の typed-adapter Dijkstra | 未対応 raw NetworkX spelling は compile しません。 |
| pandas | 正確な numeric/boolean `Series.map` UDF pipeline | 手動 vectorized rewrite の方が速い場合があります。 |
| Torch CPU | 限定 float32 inference と small-batch pre/post | Inference only。training、未対応 device/dtype は対象外です。 |
| TensorFlow CPU | Eager matmul/activation/classification と small-batch pre/post | `tf.function` なし。結果を仮定しません。 |

各 case は [`cases/`](cases/) の独立 Rextio project です。Core/NumPy/NetworkX/pandas は base profile、Torch/TensorFlow は ABI/runtime 汚染を防ぐ分離 lock 環境を使います。

## 凍結履歴と公開制御

公開済み 0.1.0 Apple M4 Pro cohort は [`cohort-15fa…`](results/canonical/cohort-15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8/) に byte-immutable で残ります。clean commit [`ff7f4fe`](https://github.com/rextio/rextio-benchmark/commit/ff7f4fea34199d850bed0446a8a223ef730ddf17) から測定し、evidence commit [`e62a3f8`](https://github.com/rextio/rextio-benchmark/commit/e62a3f8fb1637f52288873fb077ba4efba0ead59) で公開しました。後の candidate 数値で置き換えません。

初期実装は全診断へ 10% stability veto を誤適用しました。保持された NumPy BLAS negative control は約 23% 変動しましたが、事前凍結した 6 headline row はすべて通過しました。ポリシーは事前宣言範囲に合わせて修正され、元の 3 report は一つも捨てず、速い replacement window も選んでいません。

Canonical evidence directory は immutable です。検証は measurement commit、正確な case set、package provenance、policy identity、raw report、evidence object、rendered Markdown、stability JSON を digest で結びます。dirty/unrelated checkout は公開できません。canonical evidence の作成・解釈前に [PUBLICATION.md](PUBLICATION.md) を読んでください。

## Report と CUDA 境界

ローカル JSON/Markdown は gitignored `results/local/` に出力されます。Build failure は `results/local/build-cpu.json`、benchmark failure は case ごとの blocker として明示されます。CI は deterministic lint、schema、statistics、lane、route、Markdown のみ検査し、長い benchmark や speed threshold は実行しません。

CUDA profile は将来の NVIDIA Linux/WSL2 実行用 scaffolding です。CPU script は導入・実行せず、このリポジトリに **CUDA 計測はありません**。macOS 証拠は CUDA support を証明できません。CUDA は non-promoting/non-certifying のままで、TensorFlow は kernel activity/runtime transfer も主張しません。

## 開発

```bash
PYTHONPATH=src profiles/base/.venv/bin/ruff check src tests cases
PYTHONPATH=src profiles/base/.venv/bin/python -m pytest
```

- [変更履歴](CHANGELOG.md) · [公開ポリシー](PUBLICATION.md) · [セキュリティ](SECURITY.md) · [コントリビューション](CONTRIBUTING.md) · [MIT ライセンス](LICENSE)
