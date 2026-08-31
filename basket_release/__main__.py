from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import BuildError, acquire, build, build_integration, load_locked_sources, validate_candidate
from .v2_core import build_v2, build_v2_integration, validate_v2_candidate


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and validate regional basket candidates")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("source-probe", "source-lock"):
        p = sub.add_parser(name); p.add_argument("--registry", type=Path, default=Path("contracts/source_registry.json")); p.add_argument("--cache", type=Path, default=Path(".cache/basket_sources")); p.add_argument("--lock", type=Path, default=Path("run/source_lock.json"))
    p=sub.add_parser("source-lock-check"); p.add_argument("lock",type=Path)
    for name in ("build","build-v2"):
        p=sub.add_parser(name); p.add_argument("--source-lock",type=Path,required=True); p.add_argument("--price-release",type=Path,required=True); p.add_argument("--output",type=Path,default=Path("artifacts/basket_releases")); p.add_argument("--integration-output",type=Path,default=Path("artifacts/integration"))
        if name == "build-v2": p.add_argument("--allow-thin-price-coverage",action="store_true")
    for name in ("validate","validate-v2"):
        p=sub.add_parser(name); p.add_argument("release",type=Path)
    for name in ("integration","integration-v2"):
        p=sub.add_parser(name); p.add_argument("release",type=Path); p.add_argument("--output",type=Path,default=Path("artifacts/integration"))
    args=parser.parse_args()
    if args.command in {"source-probe","source-lock"}:
        result=acquire(args.registry,args.cache,args.lock if args.command=="source-lock" else None)
    elif args.command=="source-lock-check":
        lock,rows=load_locked_sources(args.lock); result={"result":"valid","snapshots":len(lock["snapshots"]),"normalized_cells":len(rows)}
    elif args.command=="build":
        release,bundle=build(args.source_lock,args.price_release,args.output,args.integration_output); result={"release":str(release),"integration_bundle":str(bundle)}
    elif args.command=="build-v2":
        release,bundle=build_v2(args.source_lock,args.price_release,args.output,args.integration_output,allow_thin_price_coverage=args.allow_thin_price_coverage); result={"release":str(release),"integration_bundle":str(bundle)}
    elif args.command=="validate": result=validate_candidate(args.release)
    elif args.command=="validate-v2": result=validate_v2_candidate(args.release)
    elif args.command=="integration-v2": result={"integration_bundle":str(build_v2_integration(args.release,args.output))}
    else: result={"integration_bundle":str(build_integration(args.release,args.output))}
    print(json.dumps(result,indent=2,sort_keys=True)); return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except (BuildError,OSError,KeyError,TypeError,ValueError,json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}",file=sys.stderr); raise SystemExit(1)
