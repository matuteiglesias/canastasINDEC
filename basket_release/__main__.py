from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import BuildError, acquire, build, build_integration, load_locked_sources, validate_candidate


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and validate regional basket candidates")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("source-probe", "source-lock"):
        p = sub.add_parser(name); p.add_argument("--registry", type=Path, default=Path("contracts/source_registry.json")); p.add_argument("--cache", type=Path, default=Path(".cache/basket_sources")); p.add_argument("--lock", type=Path, default=Path("run/source_lock.json"))
    p=sub.add_parser("source-lock-check"); p.add_argument("lock",type=Path)
    p=sub.add_parser("build"); p.add_argument("--source-lock",type=Path,required=True); p.add_argument("--price-release",type=Path,required=True); p.add_argument("--output",type=Path,default=Path("artifacts/basket_releases")); p.add_argument("--integration-output",type=Path,default=Path("artifacts/integration"))
    p=sub.add_parser("validate"); p.add_argument("release",type=Path)
    p=sub.add_parser("integration"); p.add_argument("release",type=Path); p.add_argument("--output",type=Path,default=Path("artifacts/integration"))
    args=parser.parse_args()
    if args.command in {"source-probe","source-lock"}:
        result=acquire(args.registry,args.cache,args.lock if args.command=="source-lock" else None)
    elif args.command=="source-lock-check":
        lock,rows=load_locked_sources(args.lock); result={"result":"valid","snapshots":len(lock["snapshots"]),"normalized_cells":len(rows)}
    elif args.command=="build":
        release,bundle=build(args.source_lock,args.price_release,args.output,args.integration_output); result={"release":str(release),"integration_bundle":str(bundle)}
    elif args.command=="validate": result=validate_candidate(args.release)
    else: result={"integration_bundle":str(build_integration(args.release,args.output))}
    print(json.dumps(result,indent=2,sort_keys=True)); return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except (BuildError,OSError,KeyError,TypeError,json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}",file=sys.stderr); raise SystemExit(1)
