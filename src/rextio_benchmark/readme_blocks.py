from __future__ import annotations

import re
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
        "links": ("正式報告", "測量提交", "證據提交"),
    },
}
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


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
    version_text = _format_versions(display_versions, bound_pins)
    uses_candidates = bool(bound_pins)
    outputs = {}
    for filename, locale in LOCALES.items():
        domain, source, native, ratio = locale["columns"]
        lines = [
            "<!-- rextio-benchmark:start -->",
            f"## {locale['heading']}",
            "",
            f"{locale['intro']}; **{machine}**, **{date}**, CPython "
            f"**{report['system']['python_controller']}**.",
            f"{locale['versions']}: {version_text}.",
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
            ]
        )
        if uses_candidates:
            lines.extend(["", locale["candidate_caveat"]])
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
