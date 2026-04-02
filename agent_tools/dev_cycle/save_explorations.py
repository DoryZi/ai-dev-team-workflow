"""Save research agent reports to code_explorations/ for future reuse.

Called by the /plan skill after sys-arch agents complete. Persists
their findings so future plan runs can skip already-explored dimensions.

Usage:
    uv run --directory agent_tools/dev_cycle python save_explorations.py \
        --feature "upload-retry" \
        --reports /tmp/modules.md /tmp/patterns.md \
        --dimensions modules patterns
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        description="Save research agent reports to code_explorations/.",
    )
    parser.add_argument(
        "--feature",
        required=True,
        help="Feature slug (e.g. 'upload-retry').",
    )
    parser.add_argument(
        "--reports",
        nargs="+",
        required=True,
        help="Paths to report files (one per dimension).",
    )
    parser.add_argument(
        "--dimensions",
        nargs="+",
        required=True,
        help="Dimension names matching each report (e.g. 'modules patterns boundaries').",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root (default: auto-detect from script location).",
    )
    return parser


def save_explorations(
    feature: str,
    reports: list[str],
    dimensions: list[str],
    repo_root: Path,
) -> list[Path]:
    """Save research reports to code_explorations/.

    Args:
        feature: Feature slug for filenames.
        reports: Paths to report markdown files.
        dimensions: Dimension names matching each report.
        repo_root: Repository root directory.

    Returns:
        List of paths to the saved exploration files.

    Raises:
        ValueError: If reports and dimensions have different lengths.
    """
    if len(reports) != len(dimensions):
        raise ValueError(
            f"reports ({len(reports)}) and dimensions ({len(dimensions)}) must have the same length."
        )

    output_dir = repo_root / "code_explorations"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    saved: list[Path] = []

    for report_path_str, dimension in zip(reports, dimensions):
        report_path = Path(report_path_str)

        if not report_path.exists():
            print(f"WARNING: report file not found: {report_path}", file=sys.stderr)
            continue

        content = report_path.read_text(encoding="utf-8")

        output_name = f"{timestamp}-{feature}-{dimension}.md"
        output_path = output_dir / output_name

        structured = f"""# {feature.replace('-', ' ').title()} — {dimension.title()} Exploration

**Feature**: {feature}
**Date**: {datetime.now().strftime("%Y-%m-%d %H:%M")}
**Dimension**: {dimension}

## Findings

{content}
"""
        output_path.write_text(structured, encoding="utf-8")
        saved.append(output_path)
        print(f"Saved: {output_path.relative_to(repo_root)}", file=sys.stderr)

    return saved


def main() -> int:
    """CLI entry point.

    Returns:
        Exit code: 0 for success, 1 for failure.
    """
    parser = _build_parser()
    args = parser.parse_args()

    repo_root = Path(args.repo_root) if args.repo_root else Path(__file__).resolve().parent.parent.parent

    try:
        saved = save_explorations(
            feature=args.feature,
            reports=args.reports,
            dimensions=args.dimensions,
            repo_root=repo_root,
        )
        print(f"\nSaved {len(saved)} exploration(s) to code_explorations/", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
