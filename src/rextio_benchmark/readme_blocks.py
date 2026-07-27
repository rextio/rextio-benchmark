from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .verification import GateError

HEADLINE_ROWS = (
    ("Core hybrid", "core-hybrid"),
    ("NumPy mixed fusion", "numpy-mixed-fusion"),
    ("NetworkX Dijkstra", "networkx-dijkstra"),
    ("pandas Series.map", "pandas-series-map"),
    ("PyTorch CPU deep MLP", "torch-cpu-deep-mlp"),
    ("TensorFlow CPU eager chain", "tensorflow-cpu-eager-chain"),
)

LOCALES = {
    "README.md": {
        "heading": "Verified CPU benchmark snapshot",
        "intro": "Same Python source and deterministic inputs",
        "versions": "Versions",
        "columns": ("Domain", "Python source", "Rextio native", "Speedup (source ÷ native)"),
        "caveat": (
            "These are workload-specific results, not library-wide performance claims. "
            "Build, import, first-call, and worker-process startup are excluded from "
            "these steady-state rows. The Core executable is separate because process "
            "startup is included. NumPy `dot` remains a BLAS-owned negative control; a "
            "manually vectorized pandas/NumPy rewrite may be faster. Ratios below 1× "
            "mean Rextio was slower; values near 1× indicate parity, not a material "
            "speedup."
        ),
        "candidate_caveat": (
            "Packages marked candidate are unreleased exact Git commit pins, including "
            "Core 0.1.7 and rextio-torch 0.1.3; they are not PyPI releases. "
            "The same applies to rextio-numpy 0.1.3 and rextio-tensorflow 0.1.3."
        ),
        "selection": "Selection: the chronologically first report (index 0) of exactly three qualifying publish reports; never selected by speedup.",  # noqa: E501
        "stability": "Stability: all six frozen headline rows passed the 10% stability veto.",
        "median_intro": "Three-run medians",
        "median_labels": ("Core", "NumPy", "NetworkX", "pandas", "Torch", "TensorFlow"),
        "nonclaim": "No result claims intrinsic BLAS, libtorch, TensorFlow-kernel, or CUDA acceleration.",  # noqa: E501
        "abbrev_pin": "`candidate@` labels display the first 12 hexadecimal characters only; each candidate is verified and pinned by its full 40-character Git commit.",  # noqa: E501
        "links": ("Canonical report", "measurement commit", "evidence commit"),
    },
    "README.ko.md": {
        "heading": "검증된 CPU 벤치마크 스냅샷",
        "intro": "동일한 Python 소스와 결정론적 입력",
        "versions": "버전",
        "columns": ("영역", "Python 소스", "Rextio native", "속도비 (소스 ÷ native)"),
        "caveat": (
            "각 수치는 해당 workload의 결과이며 라이브러리 전체 성능을 뜻하지 않습니다. "
            "빌드, import, 첫 호출, worker 프로세스 시작 시간은 이 steady-state "
            "행에서 제외됩니다. Core 실행 파일은 프로세스 시작을 포함하므로 별도 "
            "보고됩니다. NumPy `dot`은 BLAS negative control이며 수동 벡터화한 "
            "pandas/NumPy 재작성은 더 빠를 수 있습니다. 1× 미만은 Rextio가 더 "
            "느렸다는 뜻이며, 1× 부근의 값은 실질적인 속도 향상이 아니라 성능이 "
            "대체로 동등하다는 뜻입니다."
        ),
        "candidate_caveat": (
            "candidate로 표시된 패키지는 Core 0.1.7과 rextio-torch 0.1.3을 포함한 "
            "미배포 exact Git 커밋 핀이며 PyPI 릴리스가 아닙니다. rextio-numpy "
            "0.1.3과 rextio-tensorflow 0.1.3에도 동일하게 적용됩니다."
        ),
        "selection": "선택: 정확히 세 개의 적격 publish 보고서 중 시간순 첫 번째 보고서(index 0)를 사용하며, 속도비로 선택하지 않습니다.",  # noqa: E501
        "stability": "안정성: 고정된 여섯 headline 행은 모두 10% 안정성 veto를 통과했습니다.",
        "median_intro": "3회 실행 중앙값",
        "median_labels": ("Core", "NumPy", "NetworkX", "pandas", "Torch", "TensorFlow"),
        "nonclaim": "어떤 결과도 BLAS, libtorch, TensorFlow kernel 또는 CUDA 자체의 가속을 주장하지 않습니다.",  # noqa: E501
        "abbrev_pin": "`candidate@` 표시는 앞 12자리 16진수만 보이며, 각 candidate는 전체 40자리 Git 커밋으로 검증·고정됩니다.",  # noqa: E501
        "links": ("정식 보고서", "측정 커밋", "증거 커밋"),
    },
    "README.ja.md": {
        "heading": "検証済み CPU ベンチマーク",
        "intro": "同一の Python ソースと決定論的な入力",
        "versions": "バージョン",
        "columns": ("領域", "Python ソース", "Rextio native", "高速化 (source ÷ native)"),
        "caveat": (
            "各数値は個別 workload の結果であり、ライブラリ全体の性能を示すものでは"
            "ありません。"
            "build、import、初回呼び出し、worker 起動時間は steady-state 行から除外"
            "します。Core 実行ファイルはプロセス起動を含むため別掲です。NumPy "
            "`dot` は BLAS negative control で、手動ベクトル化 pandas/NumPy "
            "書き換えの方が速い場合があります。1× 未満は Rextio の方が遅く、"
            "1× 付近は実質的な高速化ではなく同等性能を示します。"
        ),
        "candidate_caveat": (
            "candidate と記したパッケージは Core 0.1.7 と rextio-torch 0.1.3 "
            "を含む未公開の exact Git コミット固定であり、PyPI リリースでは"
            "ありません。rextio-numpy 0.1.3 と rextio-tensorflow 0.1.3 も同様です。"
        ),
        "selection": "選択: 正確に 3 件の適格な publish レポートのうち時系列で最初のレポート（index 0）を使い、速度比では選択しません。",  # noqa: E501
        "stability": "安定性: 固定された 6 つの headline 行はすべて 10% の安定性 veto を通過しました。",  # noqa: E501
        "median_intro": "3 回実行の中央値",
        "median_labels": ("Core", "NumPy", "NetworkX", "pandas", "Torch", "TensorFlow"),
        "nonclaim": "BLAS、libtorch、TensorFlow kernel、CUDA 自体の高速化を主張する結果ではありません。",  # noqa: E501
        "abbrev_pin": "`candidate@` は先頭 12 桁の 16 進表示のみで、各 candidate は完全な 40 桁 Git コミットで検証・固定されます。",  # noqa: E501
        "links": ("正規レポート", "測定コミット", "証拠コミット"),
    },
    "README.zh-hans.md": {
        "heading": "已验证的 CPU 基准快照",
        "intro": "相同的 Python 源码和确定性输入",
        "versions": "版本",
        "columns": ("领域", "Python 源码", "Rextio native", "加速比 (source ÷ native)"),
        "caveat": (
            "这些数值仅代表对应 workload，并非对整个库的性能声明。"
            "这些 steady-state 行不含构建、import、首次调用和 worker 进程启动。"
            "Core 可执行文件因包含进程启动而单独报告。NumPy `dot` 保留为 BLAS "
            "negative control；手工向量化的 pandas/NumPy 重写可能更快。低于 "
            "1× 表示 Rextio 更慢；接近 1× 表示性能相当，而非实质性加速。"
        ),
        "candidate_caveat": (
            "标为 candidate 的包（包括 Core 0.1.7 和 rextio-torch 0.1.3）是未发布的 "
            "exact Git 提交固定，不是 PyPI 发行版；rextio-numpy 0.1.3 和 "
            "rextio-tensorflow 0.1.3 也同样如此。"
        ),
        "selection": "选择：恰好三份合格 publish 报告中按时间顺序第一份（index 0）；绝不按加速比选择。",  # noqa: E501
        "stability": "稳定性：六个固定 headline 行全部通过了 10% 稳定性 veto。",
        "median_intro": "三次运行中位数",
        "median_labels": ("Core", "NumPy", "NetworkX", "pandas", "Torch", "TensorFlow"),
        "nonclaim": "结果不声称 BLAS、libtorch、TensorFlow kernel 或 CUDA 内核本身得到加速。",
        "abbrev_pin": "`candidate@` 只显示前 12 个十六进制字符；每个 candidate 都按完整 40 字符 Git 提交验证并固定。",  # noqa: E501
        "links": ("正式报告", "测量提交", "证据提交"),
    },
    "README.zh-hant.md": {
        "heading": "已驗證的 CPU 基準快照",
        "intro": "相同的 Python 原始碼和確定性輸入",
        "versions": "版本",
        "columns": ("領域", "Python 原始碼", "Rextio native", "加速比 (source ÷ native)"),
        "caveat": (
            "這些數值僅代表對應 workload，並非對整個函式庫的效能聲明。"
            "這些 steady-state 行不含建置、import、首次呼叫和 worker 行程啟動。"
            "Core 執行檔因包含行程啟動而單獨報告。NumPy `dot` 保留為 BLAS "
            "negative control；手動向量化的 pandas/NumPy 重寫可能更快。低於 "
            "1× 表示 Rextio 較慢；接近 1× 表示效能相當，而非實質性加速。"
        ),
        "candidate_caveat": (
            "標為 candidate 的套件（包括 Core 0.1.7 和 rextio-torch 0.1.3）是未發佈的 "
            "exact Git 提交固定，不是 PyPI 發行版；rextio-numpy 0.1.3 和 "
            "rextio-tensorflow 0.1.3 也同樣如此。"
        ),
        "selection": "選擇：恰好三份合格 publish 報告中按時間順序第一份（index 0）；絕不按加速比選擇。",  # noqa: E501
        "stability": "穩定性：六個固定 headline 行全部通過了 10% 穩定性 veto。",
        "median_intro": "三次執行中位數",
        "median_labels": ("Core", "NumPy", "NetworkX", "pandas", "Torch", "TensorFlow"),
        "nonclaim": "結果不聲稱 BLAS、libtorch、TensorFlow kernel 或 CUDA 核心本身得到加速。",
        "abbrev_pin": "`candidate@` 只顯示前 12 個十六進位字元；每個 candidate 都按完整 40 字元 Git 提交驗證並固定。",  # noqa: E501
        "links": ("正式報告", "測量提交", "證據提交"),
    },
}
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class VerifiedStabilitySummary:
    """Hash-bound stability summary accepted by the README renderer."""

    document: dict[str, Any]
    logical_path: str
    sha256: str
    raw_bytes: bytes


def _finite_number(value: object, *, positive: bool = False) -> bool:
    """Return whether *value* is a JSON number accepted by the evidence contract."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and (value > 0 if positive else value >= 0)
    )


def _exact_int(value: object, expected: int) -> bool:
    """Avoid Python's ``True == 1`` identity loophole in signed evidence."""
    return type(value) is int and value == expected


def load_verified_stability_summary(
    report: dict[str, Any],
    *,
    repository_root: Path,
    report_logical_path: str,
) -> VerifiedStabilitySummary:
    """Load only the canonical bundle's hash-bound, headline-qualified summary.

    The renderer must not accept ad-hoc median values. The CLI calls
    ``verify_report`` first, then this loader validates the canonical metadata,
    digest, cohort identity, chronological selection, and six headline gates.
    """
    metadata = report.get("canonical_bundle")
    if not isinstance(metadata, dict):
        raise GateError("README blocks require canonical bundle metadata")
    logical = metadata.get("stability_summary_path")
    expected_sha = metadata.get("stability_summary_sha256")
    cohort_id = metadata.get("cohort_id")
    policy = report.get("policy")
    policy_id = policy.get("policy_id") if isinstance(policy, dict) else None
    if (
        not isinstance(logical, str)
        or not isinstance(expected_sha, str)
        or not re.fullmatch(r"[0-9a-f]{64}", expected_sha)
        or not isinstance(cohort_id, str)
        or not re.fullmatch(r"[0-9a-f]{64}", cohort_id)
    ):
        raise GateError("canonical report lacks a bound stability summary")
    if not isinstance(report_logical_path, str):
        raise GateError("canonical report path must be a logical string")
    report_path = Path(report_logical_path)
    summary_path = Path(logical)
    if (
        report_path.is_absolute()
        or summary_path.is_absolute()
        or ".." in report_path.parts
        or ".." in summary_path.parts
        or report_path.parent != summary_path.parent
        or not logical.endswith("/stability.json")
    ):
        raise GateError("canonical stability summary path is not sibling-bound")
    path = (repository_root / summary_path).resolve()
    try:
        path.relative_to(repository_root.resolve())
    except ValueError as error:
        raise GateError("canonical stability summary escapes repository") from error
    if not path.is_file():
        raise GateError("canonical stability summary is missing")
    raw = path.read_bytes()
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != expected_sha:
        raise GateError("canonical stability summary digest differs")
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as error:
        raise GateError("canonical stability summary is not JSON") from error
    if not isinstance(document, dict):
        raise GateError("canonical stability summary must be an object")
    repository = report.get("repository")
    repository_commit = repository.get("commit") if isinstance(repository, dict) else None
    if (
        not _exact_int(document.get("schema_version"), 1)
        or document.get("cohort_id") != cohort_id
        or document.get("measurement_commit") != repository_commit
        or document.get("policy_id") != policy_id
        or document.get("selection") != "chronological-first"
        or not _exact_int(document.get("selected_report_index"), 0)
        or not _exact_int(document.get("report_count"), 3)
        or not _finite_number(document.get("stability_threshold_fraction"), positive=True)
        or document.get("stability_threshold_fraction") != 0.10
    ):
        raise GateError("canonical stability summary identity differs")
    cases = document.get("cases")
    if not isinstance(cases, dict):
        raise GateError("canonical stability summary lacks cases")
    report_cases = report.get("cases")
    if not isinstance(report_cases, list):
        raise GateError("canonical report lacks a case list")
    report_case_ids = [case.get("id") for case in report_cases if isinstance(case, dict)]
    if (
        len(report_case_ids) != len(report_cases)
        or not all(isinstance(case_id, str) for case_id in report_case_ids)
        or len(set(report_case_ids)) != len(report_case_ids)
        or not all(isinstance(case_id, str) for case_id in cases)
        or set(cases) != set(report_case_ids)
    ):
        raise GateError("canonical stability summary case keys differ")
    report_by_id = {case["id"]: case for case in report_cases}
    threshold = document["stability_threshold_fraction"]
    for case_id in report_case_ids:
        record = cases.get(case_id)
        speedups = record.get("median_speedups") if isinstance(record, dict) else None
        median = record.get("three_run_median") if isinstance(record, dict) else None
        deviations = record.get("relative_deviations") if isinstance(record, dict) else None
        deviation = record.get("maximum_relative_deviation") if isinstance(record, dict) else None
        paired = report_by_id[case_id].get("paired")
        selected_speedup = paired.get("median_speedup") if isinstance(paired, dict) else None
        if (
            not isinstance(record, dict)
            or not isinstance(speedups, list)
            or len(speedups) != 3
            or not all(_finite_number(value, positive=True) for value in speedups)
            or not _finite_number(median, positive=True)
            or not isinstance(deviations, list)
            or len(deviations) != 3
            or not all(_finite_number(value) for value in deviations)
            or not _finite_number(deviation)
            or not _finite_number(selected_speedup, positive=True)
        ):
            raise GateError(f"canonical stability summary rejects case {case_id}")
        recomputed_median = statistics.median(speedups)
        recomputed_deviations = [
            abs(value - recomputed_median) / recomputed_median for value in speedups
        ]
        recomputed_maximum = max(recomputed_deviations)
        expected_headline = case_id in {headline_id for _, headline_id in HEADLINE_ROWS}
        expected_within_threshold = recomputed_maximum <= threshold + 1e-12
        if (
            median != recomputed_median
            or deviations != recomputed_deviations
            or deviation != recomputed_maximum
            or speedups[0] != selected_speedup
            or record.get("headline_gate") is not expected_headline
            or record.get("within_threshold") is not expected_within_threshold
            or (expected_headline and not expected_within_threshold)
        ):
            raise GateError(f"canonical stability summary arithmetic differs for {case_id}")
    return VerifiedStabilitySummary(
        document=document,
        logical_path=logical,
        sha256=actual_sha,
        raw_bytes=raw,
    )


def _format_versions(
    versions: dict[str, str],
    bound_pins: dict[str, dict[str, str]],
) -> str:
    parts: list[str] = []
    for name in sorted(versions):
        version = versions[name]
        pin = bound_pins.get(name)
        if pin is not None and version == pin["version"]:
            parts.append(f"{name} {version} candidate@{pin['rev'][:12]}")
        else:
            parts.append(f"{name} {version}")
    return ", ".join(parts)


def generate_blocks(
    report: dict[str, Any],
    *,
    report_logical_path: str,
    measurement_commit: str,
    evidence_commit: str,
    github_url: str,
    repository_root: Path,
) -> dict[str, str]:
    if not report.get("publishable") or report.get("canonical_bundle") is None:
        raise GateError("README blocks require a verified canonical publish report")
    if report["repository"]["commit"] != measurement_commit:
        raise GateError("measurement commit differs from canonical report")
    if not _COMMIT.fullmatch(measurement_commit) or not _COMMIT.fullmatch(evidence_commit):
        raise GateError("README commit arguments must be full lowercase Git commits")
    base = github_url.rstrip("/")
    if not base.startswith("https://github.com/"):
        raise GateError("GitHub URL must use https://github.com/")
    cases = {case["id"]: case for case in report["cases"]}
    if any(case_id not in cases for _, case_id in HEADLINE_ROWS):
        raise GateError("canonical report lacks a frozen headline row")
    # Full-report diagnostics (e.g. phase1) must never enter the six-row block.
    markdown_path = report["canonical_bundle"].get("report_markdown_path")
    if not isinstance(markdown_path, str) or not markdown_path.endswith("/report.md"):
        raise GateError("canonical report lacks its bound Markdown path")
    if Path(markdown_path).parent != Path(report_logical_path).parent:
        raise GateError("canonical JSON and Markdown reports use different bundle roots")
    report_url = f"{base}/blob/{evidence_commit}/{markdown_path}"
    measurement_url = f"{base}/commit/{measurement_commit}"
    evidence_url = f"{base}/commit/{evidence_commit}"
    host = report["system"]["host"]
    machine = " / ".join(dict.fromkeys((host["model"], host["cpu_brand"])))
    date = report["generated_at"][:10]
    # Display list: last-wins is fine for labels of non-candidate rextio packages.
    # Candidate presence/conflicts use report_package_versions (fail closed).
    display_versions = {
        name: version
        for case in report["cases"]
        for name, version in case["packages"].items()
        if name == "rextio" or name.startswith("rextio-")
    }
    # Candidate@REV labels and caveats come only from verified bound policy/provenance.
    # Non-released publishable/canonical reports require the full frozen candidate set;
    # authentic released frozen reports stay unlabeled. Version strings alone never
    # imply candidacy.
    from .integration_targets import TARGET_PACKAGE_VERSIONS, TARGET_POLICY_ID
    from .provenance import (
        bound_candidate_pins_from_report,
        candidate_plugins_in_versions,
        full_candidate_plugin_pins,
        is_released_frozen_report,
        report_named_package_versions,
        report_package_versions,
    )

    if is_released_frozen_report(report):
        bound_pins: dict[str, dict[str, str]] = {}
    else:
        policy = report.get("policy")
        next_policy = isinstance(policy, dict) and policy.get("policy_id") == TARGET_POLICY_ID
        if next_policy:
            expected_names = set(TARGET_PACKAGE_VERSIONS)
            versions = report_named_package_versions(report, expected_names)
            present_names = {
                name
                for name, version in versions.items()
                if version == TARGET_PACKAGE_VERSIONS[name]
            }
        else:
            candidate_versions = report_package_versions(report)
            present = candidate_plugins_in_versions(candidate_versions)
            expected_names = set(full_candidate_plugin_pins())
            present_names = set(present)
        if present_names != expected_names:
            set_label = "package" if next_policy else "plugin"
            raise GateError(
                "README blocks for non-released reports require the full frozen "
                f"candidate {set_label} set "
                f"(expected {sorted(expected_names)}, found {sorted(present_names)})"
            )
        if report.get("policy") is None or report.get("package_provenance") is None:
            raise GateError(
                "README blocks for candidate versions require bound policy and package_provenance"
            )
        bound_pins = bound_candidate_pins_from_report(report)
        if set(bound_pins) != expected_names or set(bound_pins) != present_names:
            raise GateError("README candidate policy pins do not match the full candidate set")
    stability_summary = load_verified_stability_summary(
        report,
        repository_root=repository_root,
        report_logical_path=report_logical_path,
    )
    summary = stability_summary.document
    if summary.get("measurement_commit") != measurement_commit:
        raise GateError("stability summary measurement commit differs")
    version_text = _format_versions(display_versions, bound_pins)
    uses_candidates = bool(bound_pins)
    outputs = {}
    for filename, locale in LOCALES.items():
        domain, source, native, ratio = locale["columns"]
        three_run_medians = "; ".join(
            f"{label} {summary['cases'][case_id]['three_run_median']:.3f}×"
            for label, (_, case_id) in zip(locale["median_labels"], HEADLINE_ROWS, strict=True)
        )
        lines = [
            "<!-- rextio-benchmark:start -->",
            f"## {locale['heading']}",
            "",
            f"{locale['intro']}; **{machine}**, **{date}**, CPython "
            f"**{report['system']['python_controller']}**.",
            f"{locale['versions']}: {version_text}.",
            locale["selection"],
            f"{locale['stability']} {locale['median_intro']}: {three_run_medians}.",
            "",
            f"| {domain} | {source} | {native} | {ratio} |",
            "| --- | ---: | ---: | ---: |",
        ]
        for label, case_id in HEADLINE_ROWS:
            case = cases[case_id]
            source_ms = case["lanes"]["python-source"]["steady_state"]["median_ns"] / 1e6
            native_ms = case["lanes"]["rextio-native"]["steady_state"]["median_ns"] / 1e6
            speedup = case["paired"]["median_speedup"]
            lines.append(f"| {label} | {source_ms:.6f} ms | {native_ms:.6f} ms | {speedup:.3f}× |")
        links = locale["links"]
        lines.extend(
            [
                "",
                locale["caveat"],
                locale["nonclaim"],
            ]
        )
        if uses_candidates:
            lines.extend(
                [
                    "",
                    locale["candidate_caveat"],
                    locale["abbrev_pin"],
                ]
            )
        lines.extend(
            [
                "",
                f"[{links[0]}]({report_url}) · [{links[1]}]({measurement_url}) · "
                f"[{links[2]}]({evidence_url})",
                "<!-- rextio-benchmark:end -->",
                "",
            ]
        )
        outputs[filename] = "\n".join(lines)
    return outputs


def write_blocks(output_dir: Path, blocks: dict[str, str]) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for filename, content in blocks.items():
        path = output_dir / filename
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    return paths
