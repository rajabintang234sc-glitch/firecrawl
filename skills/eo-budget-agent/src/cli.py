"""Headless analysis and exports. No third-party Python dependencies."""

import argparse
import json
import sys
from pathlib import Path

from engine import ROOT, analyze
from exports import export_csv, export_proposal
from validation import ValidationError, validate_project


def main():
    parser = argparse.ArgumentParser(description="EO budget multi-agent: RAB, HPP, pricing, creative, operations")
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "sample-project.json")
    parser.add_argument("--output", type=Path, help="Output file; otherwise write JSON to stdout")
    parser.add_argument("--format", choices=("json", "csv", "proposal"), default="json")
    args = parser.parse_args()
    try:
        project = validate_project(json.loads(args.input.read_text(encoding="utf-8")))
        report = analyze(project)
        content = export_csv(project, report) if args.format == "csv" else export_proposal(project, report) if args.format == "proposal" else json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content, encoding="utf-8")
        else:
            print(content, end="")
        return 0
    except (ValidationError, ValueError, OSError) as error:
        print(f"Gagal: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
