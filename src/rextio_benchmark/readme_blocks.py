from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .verification import GateError

HEADLINE_ROWS = (
    ("Core", "core-hybrid"),
    ("NumPy", "numpy-mixed-fusion"),
    ("NetworkX", "networkx-dijkstra"),
    ("pandas", "pandas-series-map"),
    ("PyTorch CPU", "torch-cpu-deep-mlp"),
    ("TensorFlow CPU", "tensorflow-cpu-eager-chain"),
)
LOCALES = {
    "README.md": {
        "heading": "Verified CPU benchmark snapshot",
        "intro": "Same Python source and deterministic inputs",
        "columns": ("Domain", "Python source", "Rextio native", "Speedup (source ÷ native)"),
        "caveat": (
            "Build, import, first-call, and worker-process startup are excluded from "
            "these steady-state rows. The Core executable is separate because process "
            "startup is included. NumPy `dot` remains a BLAS-owned negative control; a "
            "manually vectorized pandas/NumPy rewrite may be faster."
        ),
        "links": ("Canonical report", "measurement commit", "evidence commit"),
    },
    "README.ko.md": {
        "heading": "검증된 CPU 벤치마크 스냅샷",
        "intro": "동일한 Python 소스와 결정적 입력",
        "columns": ("영역", "Python 소스", "Rextio native", "속도비 (소스 ÷ native)"),
        "caveat": (
            "빌드, import, 첫 호출, worker 프로세스 시작 시간은 이 steady-state "
            "행에서 제외됩니다. Core 실행 파일은 프로세스 시작을 포함하므로 별도 "
            "보고됩니다. NumPy `dot`은 BLAS negative control이며 수동 벡터화한 "
            "pandas/NumPy 재작성은 더 빠를 수 있습니다."
        ),
        "links": ("정식 보고서", "측정 커밋", "증거 커밋"),
    },
    "README.ja.md": {
        "heading": "検証済み CPU ベンチマーク",
        "intro": "同一の Python ソースと決定的入力",
        "columns": ("領域", "Python ソース", "Rextio native", "高速化 (source ÷ native)"),
        "caveat": (
            "build、import、初回呼び出し、worker 起動時間は steady-state 行から除外"
            "します。Core 実行ファイルはプロセス起動を含むため別掲です。NumPy "
            "`dot` は BLAS negative control で、手動ベクトル化 pandas/NumPy "
            "書き換えの方が速い場合があります。"
        ),
        "links": ("正規レポート", "測定コミット", "証拠コミット"),
    },
    "README.zh-hans.md": {
        "heading": "已验证的 CPU 基准快照",
        "intro": "相同的 Python 源码和确定性输入",
        "columns": ("领域", "Python 源码", "Rextio native", "加速比 (source ÷ native)"),
        "caveat": (
            "这些 steady-state 行不含构建、import、首次调用和 worker 进程启动。"
            "Core 可执行文件因包含进程启动而单独报告。NumPy `dot` 保留为 BLAS "
            "negative control；手工向量化的 pandas/NumPy 重写可能更快。"
        ),
        "links": ("规范报告", "测量提交", "证据提交"),
    },
    "README.zh-hant.md": {
        "heading": "已驗證的 CPU 基準快照",
        "intro": "相同的 Python 原始碼和確定性輸入",
        "columns": ("領域", "Python 原始碼", "Rextio native", "加速比 (source ÷ native)"),
        "caveat": (
            "這些 steady-state 行不含建置、import、首次呼叫和 worker 行程啟動。"
            "Core 執行檔因包含行程啟動而單獨報告。NumPy `dot` 保留為 BLAS "
            "negative control；手動向量化的 pandas/NumPy 重寫可能更快。"
        ),
        "links": ("規範報告", "測量提交", "證據提交"),
    },
}
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


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
    report_url = f"{base}/blob/{evidence_commit}/{report_logical_path}"
    measurement_url = f"{base}/commit/{measurement_commit}"
    evidence_url = f"{base}/commit/{evidence_commit}"
    host = report["system"]["host"]
    machine = " / ".join(dict.fromkeys((host["model"], host["cpu_brand"])))
    date = report["generated_at"][:10]
    versions = {
        name: version
        for case in report["cases"]
        for name, version in case["packages"].items()
        if name == "rextio" or name.startswith("rextio-")
    }
    version_text = ", ".join(f"{name} {versions[name]}" for name in sorted(versions))
    outputs = {}
    for filename, locale in LOCALES.items():
        domain, source, native, ratio = locale["columns"]
        lines = [
            "<!-- rextio-benchmark:start -->",
            f"## {locale['heading']}",
            "",
            f"{locale['intro']}; **{machine}**, **{date}**, CPython "
            f"**{report['system']['python_controller']}**.",
            f"Versions: {version_text}.",
            "",
            f"| {domain} | {source} | {native} | {ratio} |",
            "| --- | ---: | ---: | ---: |",
        ]
        for label, case_id in HEADLINE_ROWS:
            case = cases[case_id]
            source_ms = case["lanes"]["python-source"]["steady_state"]["median_ns"] / 1e6
            native_ms = case["lanes"]["rextio-native"]["steady_state"]["median_ns"] / 1e6
            speedup = case["paired"]["median_speedup"]
            lines.append(
                f"| {label} | {source_ms:.6f} ms | {native_ms:.6f} ms | {speedup:.3f}× |"
            )
        links = locale["links"]
        lines.extend(
            [
                "",
                locale["caveat"],
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
