"""CLI for the bounded ENGHo/Engel Phase-A surface."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from basket_release.core import BuildError
from .artifact import build_reference_artifact, validate_reference_artifact
from .commissioning import commission_reference_artifact


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m basket_release.engel")
    sub = p.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build-reference", help="build candidate ENGHo reference expenditure structure")
    build.add_argument("--engho-release", type=Path, required=True)
    build.add_argument("--output", type=Path, default=Path("artifacts/engel_reference"))
    build.add_argument("--upstream-receipt", type=Path)

    validate = sub.add_parser("validate-reference", help="validate candidate reference structure")
    validate.add_argument("release", type=Path)

    commission = sub.add_parser("commission-reference", help="run G1-G4 Phase-A commissioning")
    commission.add_argument("--release", type=Path, required=True)
    commission.add_argument("--output", type=Path, required=True)
    commission.add_argument("--benchmarks", type=Path)

    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    if args.command == "build-reference":
        result = {
            "release": str(build_reference_artifact(
                args.engho_release,
                args.output,
                upstream_receipt=args.upstream_receipt,
            ))
        }
    elif args.command == "validate-reference":
        result = validate_reference_artifact(args.release)
    else:
        result = {
            "commissioning": str(commission_reference_artifact(
                args.release,
                args.output,
                benchmark_registry=args.benchmarks,
            ))
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BuildError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
