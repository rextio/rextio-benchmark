# rextio-benchmark

<p align="center"><img src="./assets/readme/rextio-icon.png" width="104" alt="Rextio benchmark 아이콘"></p>
<p align="center"><strong>원본 Python 소스, 생성된 fallback, 검증된 Rextio native 경로를<br>감사 가능하게 비교하는 CPU 우선 벤치마크입니다.</strong></p>

<p align="center"><a href="README.md">English</a> · <a href="README.ko.md">한국어</a> · <a href="README.zh-hans.md">简体中文</a> · <a href="README.zh-hant.md">繁體中文</a> · <a href="README.ja.md">日本語</a></p>

<p align="center"><img alt="GitHub 저장소 버전 0.1.1" src="https://img.shields.io/badge/repository-0.1.1-24292f"> <a href="LICENSE"><img alt="MIT 라이선스" src="https://img.shields.io/badge/license-MIT-blue"></a></p>

이 저장소는 헤드라인 하나가 아니라 재현 가능한 Rextio 성능 증거를 원하는 개발자와 검토자를 위한 것입니다. **Rextio Core와 다섯 개의 first-party plugin**(NumPy, NetworkX, pandas, Torch, TensorFlow)을 다루며 provenance, route 증거, 정확성 검사, 진단, 동급 성능, 느린 결과를 모두 공개합니다.

```bash
scripts/run.sh quick
```

이 명령은 짧은 sample로 전체 harness를 실행합니다. Quick mode는 의도적으로 **게시할 수 없습니다**.

`rextio-benchmark`는 GitHub로만 배포됩니다. 저장소 버전 **0.1.1**에는 tag나 PyPI package가 없습니다.

## 증거: 최신 canonical CPU cohort

**Mac16,11 / Apple M4 Pro**, **2026-07-26**, CPython **3.11.9**에서 clean commit [`92ef027`](https://github.com/rextio/rextio-benchmark/commit/92ef027cea25f9d6bf1d730de4c226d40016ba6e)을 측정한 연속 세 번의 실행입니다. 첫 보고서는 속도가 아니라 시간 순서로 선택했습니다.

| 도메인 | 세 번 실행 중앙 속도비 | 최대 편차 |
| --- | ---: | ---: |
| Core hybrid | 57.729× | 1.31% |
| NumPy mixed fusion | 2.523× | 3.88% |
| NetworkX Dijkstra | 3.679× | 1.09% |
| pandas `Series.map` | 66.143× | 0.92% |
| PyTorch CPU deep MLP | 1.017× | 0.41% |
| TensorFlow CPU eager chain | 1.040× | 0.38% |

미리 선언한 여섯 headline row가 모두 10% 안정성 gate를 통과했습니다. 이는 **특정 워크로드 관측값**이며 라이브러리 전체의 속도 향상, 릴리스, 지원, 개별 변경의 인과적 A/B 주장이 아닙니다. 1× 부근은 동급입니다.

같은 canonical 보고서는 불리한 진단도 유지합니다. NumPy non-fused phase 1 **0.248×**, NumPy `dot` BLAS negative control **0.587×**, NumPy F64 direct-sink boundary **0.305×**, TensorFlow small-batch pre/post **0.494×**입니다. 1× 미만은 실패한 보고서가 아니라 유효한 증거입니다.

- [Canonical bundle](results/canonical/cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec/)
- [시간 순서상 첫 보고서](results/canonical/cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec/report.md)
- [안정성 요약](results/canonical/cohort-15e2f2527664ea2ed5c36e0c03b054ea6da69d1e476c07934727c252b947ccec/stability.json)
- [고정된 게시 정책](PUBLICATION.md)

## 실제 비교 대상

각 timing lane은 새 process로 시작합니다.

```text
python-source    → cases/<case>/src 아래의 변경하지 않은 module
rextio-fallback  → REXTIO_NATIVE_MODE=fallback인 생성 package
rextio-native    → native mode를 강제하고 threshold를 끈 동일 package
```

측정 전 controller는 정확한 `native-direct` 또는 `native-plugin:*` route, `native_status=accepted`, 빌드된 native artifact, 예상 generated-source 증거, 올바른 출력을 요구합니다. stale import를 거부하고 source/build 증거를 hash하며 환경을 sanitize하고, deterministic input은 timed region 밖에서 만들고, import/first-call 시간을 steady-state sample과 별도로 기록합니다.

Harness는 숫자를 만들어 넣거나 불리한 결과를 버리거나 sliding window를 쓰거나 성능을 test threshold로 다루지 않습니다. 원본 source, generated fallback, native 출력은 각 case의 exact 또는 numeric 비교 조건을 통과해야 합니다.

## 첫 로컬 실행

요구 사항:

- CPython **3.11 only** (`>=3.11,<3.12`)
- [uv](https://docs.astral.sh/uv/)
- `cargo`, `rustc`를 포함한 stable Rust
- 격리된 Torch/TensorFlow 환경을 위한 충분한 disk

```bash
scripts/run.sh quick
```

더 느린 진단용 게시 시도 한 번:

```bash
scripts/run.sh publish
```

고정된 세 번의 시도로만 candidate canonical bundle을 만듭니다.

```bash
scripts/run.sh cohort
```

Bootstrap, build, benchmark, schema, evidence, correctness, route, clean-commit 또는 mode별 게시 검사 중 하나라도 실패하면 wrapper가 0이 아닌 코드로 종료합니다. 큰 speedup만으로 `results/canonical/`에 보고서를 복사할 수 없습니다.

진단용 개별 단계:

```bash
scripts/bootstrap.sh cpu
scripts/build.sh cpu
scripts/benchmark.sh cpu quick
scripts/verify.sh results/local/benchmark-quick-YYYYMMDDTHHMMSSZ.json
```

## 측정 package provenance

최신 0.1.1 cohort는 측정 당시의 정확한 **pre-release Git candidate 네 개**와 PyPI 배포물 두 개를 측정했습니다. 나중에 동일한 version이 배포되어도 이 역사적 증거는 바뀌지 않습니다.

| Package | 측정 상태 | 정확한 Git commit |
| --- | --- | --- |
| `rextio` | 0.1.7 candidate | `b8b8ed11f6b7b7aae4c7ae5205d88529608e8e97` |
| `rextio-numpy` | 0.1.3 candidate | `cf461e6775780a598517980c555a1aec079285d8` |
| `rextio-networkx` | 0.1.1 released PyPI | `ffc8681756d6f690ac090fe6b03f6ba220896ded` |
| `rextio-pandas` | 0.1.2 released PyPI | `930a4fbfbd084a9869dbbf521770e811ea3d6652` |
| `rextio-torch` | 0.1.3 candidate | `1e92b24b154c7266dc37d19533fc3e17a8b05f9a` |
| `rextio-tensorflow` | 0.1.3 candidate | `1fdb2e1cd91d058a056db76c2e0a15d52c855053` |

정확한 source 선언은 [`profiles/next-candidate.toml`](profiles/next-candidate.toml)에 있습니다. NetworkX/pandas commit은 release tag를 가리키며 나머지 네 행은 이후 PyPI artifact가 아닙니다.

## Case와 해석

| Case | 보여 주는 것 | 제한 |
| --- | --- | --- |
| Core hybrid / executable | Scalar 산술·중첩 제어 흐름, 별도의 닫힌 Rust process | Wrapper/process overhead가 포함됩니다. |
| NumPy fusion | `(left + right) * (left - right)` | Fusion rule과 generated helper 증거가 필요합니다. |
| NumPy phase 1 / direct sink / `dot` | Non-fused branch, boundary allocation, BLAS negative control | 진단 전용이며 phase 1은 fusion claim이 아니고 speedup을 전제하지 않습니다. |
| NetworkX | Deterministic graph의 typed-adapter Dijkstra | 지원하지 않는 raw NetworkX spelling은 컴파일하지 않습니다. |
| pandas | 정확한 numeric/boolean `Series.map` UDF pipeline | 수동 vectorized rewrite가 더 빠를 수 있습니다. |
| Torch CPU | 제한된 float32 inference와 small-batch pre/post | Inference only; training이나 지원하지 않는 device/dtype은 제외합니다. |
| TensorFlow CPU | Eager matmul/activation/classification과 small-batch pre/post | `tf.function` 없음; 결과를 전제하지 않습니다. |

각 case는 [`cases/`](cases/) 아래의 독립 Rextio project입니다. Core/NumPy/NetworkX/pandas는 base profile을, Torch/TensorFlow는 ABI/runtime 오염을 막기 위한 격리된 lock 환경을 사용합니다.

## 고정된 역사와 게시 통제

배포된 0.1.0 Apple M4 Pro cohort는 [`cohort-15fa…`](results/canonical/cohort-15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8/)에 byte-immutable로 남습니다. clean commit [`ff7f4fe`](https://github.com/rextio/rextio-benchmark/commit/ff7f4fea34199d850bed0446a8a223ef730ddf17)에서 측정했고 evidence commit [`e62a3f8`](https://github.com/rextio/rextio-benchmark/commit/e62a3f8fb1637f52288873fb077ba4efba0ead59)에 게시했습니다. 이후 candidate 숫자가 이를 대체하지 않습니다.

첫 구현은 모든 진단에 10% 안정성 veto를 잘못 적용했습니다. 유지된 NumPy BLAS negative control 편차는 약 23%였지만 미리 고정한 headline 여섯 행은 모두 통과했습니다. 정책은 사전 선언 범위에 맞게 수정되었고, 원래 세 보고서는 하나도 버리지 않았으며 더 빠른 replacement window도 선택하지 않았습니다.

Canonical evidence directory는 immutable입니다. 검증은 measurement commit, 정확한 case set, package provenance, policy identity, raw report, evidence object, rendered Markdown, stability JSON을 digest로 묶습니다. dirty/unrelated checkout은 게시할 수 없습니다. Canonical 증거를 만들거나 해석하기 전에 [PUBLICATION.md](PUBLICATION.md)를 읽으세요.

## 보고서와 CUDA 경계

Local JSON/Markdown report는 gitignored `results/local/`에 기록됩니다. Build 실패는 `results/local/build-cpu.json`에, benchmark 실패는 case별 blocker로 남습니다. CI는 deterministic lint, schema, statistics, lane, route, Markdown을 검사하지만 긴 benchmark나 speed threshold는 실행하지 않습니다.

CUDA profile은 미래 NVIDIA Linux/WSL2 실행을 위한 scaffolding입니다. CPU script는 이를 설치하거나 실행하지 않으며 이 저장소에는 **CUDA 측정이 없습니다**. macOS 증거로 CUDA 지원을 입증할 수 없습니다. CUDA는 non-promoting/non-certifying이며 TensorFlow는 kernel activity/runtime transfer claim도 하지 않습니다.

## 개발

```bash
PYTHONPATH=src profiles/base/.venv/bin/ruff check src tests cases
PYTHONPATH=src profiles/base/.venv/bin/python -m pytest
```

- [변경 기록](CHANGELOG.md) · [게시 정책](PUBLICATION.md) · [보안](SECURITY.md) · [기여](CONTRIBUTING.md) · [MIT 라이선스](LICENSE)
