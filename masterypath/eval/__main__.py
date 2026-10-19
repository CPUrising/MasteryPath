"""CLI: ``python -m masterypath.eval outline --cases cases.jsonl [--baseline b.json]``.

Deterministic, offline metrics for generated outlines (ADR-018 / spec 09).
Exit code is non-zero when a metric falls below its threshold or regresses
against the baseline.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from masterypath.eval.outline_eval import evaluate_cases, load_cases

_MIN_F1 = 0.8
_TOLERANCE = 0.05


def _cmd_outline(args: argparse.Namespace) -> int:
    cases = load_cases(args.cases)
    report = evaluate_cases(cases)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    failed = False
    if report["mean_kp_f1"] < args.min_f1:
        print(f"FAIL: mean_kp_f1 {report['mean_kp_f1']:.3f} < {args.min_f1}", file=sys.stderr)
        failed = True
    if not report["all_acyclic"]:
        print("FAIL: prerequisite cycle detected", file=sys.stderr)
        failed = True
    if not report["all_in_bounds"]:
        print("FAIL: knowledge-point count out of bounds", file=sys.stderr)
        failed = True

    if args.baseline:
        baseline = json.loads(open(args.baseline, encoding="utf-8").read())
        if report["mean_kp_f1"] < baseline.get("mean_kp_f1", 0.0) - _TOLERANCE:
            print("FAIL: regression vs baseline", file=sys.stderr)
            failed = True

    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="masterypath.eval")
    sub = parser.add_subparsers(dest="command", required=True)
    outline = sub.add_parser("outline", help="score generated outlines against a golden set")
    outline.add_argument("--cases", required=True)
    outline.add_argument("--baseline")
    outline.add_argument("--min-f1", type=float, default=_MIN_F1)
    outline.set_defaults(func=_cmd_outline)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
