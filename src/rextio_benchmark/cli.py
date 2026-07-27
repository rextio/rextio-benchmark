from __future__ import annotations

import argparse
from pathlib import Path

from .build_runner import build_cpu
from .bundler import bundle_cohort, bundle_report
from .readme_blocks import generate_blocks, write_blocks
from .report import run_suite
from .verifier import verify_report


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="rextio-benchmark")
    subparsers = result.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="build all CPU case projects")
    build.add_argument("platform", choices=["cpu"])
    benchmark = subparsers.add_parser("benchmark", help="run benchmark cases")
    benchmark.add_argument("platform", choices=["cpu"])
    benchmark.add_argument("mode", choices=["quick", "publish"])
    verify = subparsers.add_parser("verify", help="validate a report and its evidence")
    verify.add_argument("report", type=Path)
    bundle = subparsers.add_parser(
        "bundle",
        help="copy verified run outputs into a canonical evidence bundle",
    )
    bundle.add_argument("report", type=Path)
    bundle.add_argument("--name")
    cohort = subparsers.add_parser(
        "cohort",
        help="verify and bundle exactly three chronological publish reports",
    )
    cohort.add_argument("reports", nargs=3, type=Path)
    blocks = subparsers.add_parser(
        "readme-blocks",
        help="render five localized Core README marker blocks",
    )
    blocks.add_argument("report", type=Path)
    blocks.add_argument("--measurement-commit", required=True)
    blocks.add_argument("--evidence-commit", required=True)
    blocks.add_argument("--github-url", required=True)
    blocks.add_argument("--output-dir", required=True, type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    root = repository_root()
    if arguments.command == "build":
        report, success = build_cpu(root)
        for project in report["projects"]:
            print(f"{project['project']}: {project['status']}")
        print(root / "results" / "local" / "build-cpu.json")
        return 0 if success else 1
    if arguments.command == "benchmark":
        report, path = run_suite(root, arguments.mode)
        print(path)
        for case in report["cases"]:
            print(f"{case['id']}: {'passed' if case['eligible'] else 'blocked'}")
        return 0 if all(case["eligible"] for case in report["cases"]) else 1
    if arguments.command == "verify":
        report = verify_report(arguments.report.resolve(), root)
        print(
            f"valid benchmark report v{report['schema_version']}: "
            f"{len(report['cases'])} cases, publishable={report['publishable']}"
        )
        return 0
    if arguments.command == "cohort":
        report_path, manifest_path, stability_path, summary = bundle_cohort(
            [path.resolve() for path in arguments.reports],
            root,
        )
        print(report_path)
        print(manifest_path)
        print(stability_path)
        return 0
    if arguments.command == "readme-blocks":
        report_path = arguments.report.resolve()
        report = verify_report(report_path, root)
        logical = report_path.relative_to(root.resolve()).as_posix()
        paths = write_blocks(
            arguments.output_dir.resolve(),
            generate_blocks(
                report,
                report_logical_path=logical,
                measurement_commit=arguments.measurement_commit,
                evidence_commit=arguments.evidence_commit,
                github_url=arguments.github_url,
                repository_root=root,
            ),
        )
        for path in paths:
            print(path)
        return 0
    report_path, manifest_path, summary = bundle_report(
        arguments.report.resolve(), root, name=arguments.name
    )
    print(report_path)
    print(manifest_path)
    print(
        f"{summary['file_count']} roles, {summary['object_count']} objects, "
        f"{summary['logical_bytes']} logical bytes, {summary['stored_bytes']} stored bytes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
