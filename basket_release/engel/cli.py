"""CLI for the bounded ENGHo/Engel research surfaces."""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

from basket_release.core import BuildError
from .artifact import build_reference_artifact, validate_reference_artifact
from .commissioning import commission_reference_artifact
from .phase_b_artifact import build_sensitivity_artifact, validate_sensitivity_artifact
from .phase_b_commissioning import commission_sensitivity_artifact
from .cedlas_dt370 import build_replication_artifact, validate_replication_artifact
from .cedlas_provenance import commission_low_education_provenance
from .cedlas_old_reconstruction import reconstruct_old_method
from .cedlas_commissioning import commission_replication


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m basket_release.engel")
    sub = p.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build-reference")
    build.add_argument("--engho-release", type=Path, required=True)
    build.add_argument("--output", type=Path, default=Path("artifacts/engel_reference"))
    build.add_argument("--upstream-receipt", type=Path)

    validate = sub.add_parser("validate-reference")
    validate.add_argument("release", type=Path)

    commission = sub.add_parser("commission-reference")
    commission.add_argument("--release", type=Path, required=True)
    commission.add_argument("--output", type=Path, required=True)
    commission.add_argument("--benchmarks", type=Path)

    paths = sub.add_parser("build-paths")
    paths.add_argument("--reference-release", type=Path, required=True)
    paths.add_argument("--ipc-release", type=Path, required=True)
    paths.add_argument("--official-basket-release", type=Path, required=True)
    paths.add_argument("--output", type=Path, default=Path("artifacts/engel_sensitivity"))

    validate_paths = sub.add_parser("validate-paths")
    validate_paths.add_argument("release", type=Path)

    commission_paths = sub.add_parser("commission-paths")
    commission_paths.add_argument("--release", type=Path, required=True)
    commission_paths.add_argument("--output", type=Path, required=True)
    commission_paths.add_argument("--benchmarks", type=Path)

    cedlas = sub.add_parser("build-cedlas-dt370")
    cedlas.add_argument("--ipc-release", type=Path, required=True)
    cedlas.add_argument("--official-basket-release", type=Path, required=True)
    cedlas.add_argument("--output", type=Path, required=True)
    cedlas.add_argument("--coicop02-food-fraction", default="1")
    cedlas.add_argument("--regionalization", choices=["paper_published_ratio","table2_exact_ratio_to_2_52"], default="paper_published_ratio")

    cedlas_validate = sub.add_parser("validate-cedlas-dt370")
    cedlas_validate.add_argument("release", type=Path)

    cedlas_commission = sub.add_parser("commission-cedlas-dt370")
    cedlas_commission.add_argument("--release", type=Path, required=True)
    cedlas_commission.add_argument("--output", type=Path, required=True)

    cedlas_provenance = sub.add_parser("cedlas-low-education-provenance")
    cedlas_provenance.add_argument("--engho-release", type=Path, required=True)
    cedlas_provenance.add_argument("--output", type=Path, required=True)

    cedlas_old = sub.add_parser("cedlas-old-method-reconstruction")
    cedlas_old.add_argument("--ipc-release", type=Path, required=True)
    cedlas_old.add_argument("--official-basket-release", type=Path, required=True)
    cedlas_old.add_argument("--output", type=Path, required=True)
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    if args.command == "build-reference":
        result = {"release": str(build_reference_artifact(args.engho_release,args.output,upstream_receipt=args.upstream_receipt))}
    elif args.command == "validate-reference":
        result = validate_reference_artifact(args.release)
    elif args.command == "commission-reference":
        result = {"commissioning": str(commission_reference_artifact(args.release,args.output,benchmark_registry=args.benchmarks))}
    elif args.command == "build-paths":
        result = {"release": str(build_sensitivity_artifact(args.reference_release,args.ipc_release,args.official_basket_release,args.output))}
    elif args.command == "validate-paths":
        result = validate_sensitivity_artifact(args.release)
    elif args.command == "commission-paths":
        result = {"commissioning": str(commission_sensitivity_artifact(args.release,args.output,benchmark_registry=args.benchmarks))}
    elif args.command == "build-cedlas-dt370":
        result = {"release": str(build_replication_artifact(args.ipc_release,args.official_basket_release,args.output,coicop02_food_fraction=Decimal(args.coicop02_food_fraction),regionalization=args.regionalization))}
    elif args.command == "validate-cedlas-dt370":
        result = validate_replication_artifact(args.release)
    elif args.command == "commission-cedlas-dt370":
        result = {"commissioning": str(commission_replication(args.release,args.output))}
    elif args.command == "cedlas-low-education-provenance":
        result = {"commissioning": str(commission_low_education_provenance(args.engho_release,args.output))}
    else:
        result = {"commissioning": str(reconstruct_old_method(args.ipc_release,args.official_basket_release,args.output))}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BuildError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
