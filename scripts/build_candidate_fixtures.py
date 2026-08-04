#!/usr/bin/env python3
"""Build pinned, deterministic test inputs; values are deliberately non-real."""
import csv, hashlib, json
from pathlib import Path

ROOT=Path(__file__).parents[1]; FIX=ROOT/"fixtures/candidate_inputs"; FIX.mkdir(parents=True,exist_ok=True)
regions=("gran_buenos_aires","cuyo","noreste","noroeste","pampeana","patagonia")
def csvwrite(path, fields, rows):
    with path.open("w",newline="",encoding="utf-8") as h: w=csv.DictWriter(h,fields,lineterminator="\n");w.writeheader();w.writerows(rows)
snaps=[]
for dist,measure in (("445.1","CBA"),("446.1","CBT")):
    fields=["indice_tiempo",*regions]; rows=[]
    for y,m in [(2016,1),(2024,1),(2024,2),(2024,3)]:
        base=(y-2015)*100+m
        rows.append({"indice_tiempo":f"{y}-{m:02d}-01",**{r:str(base+i*3+(200 if measure=="CBT" else 0)) for i,r in enumerate(regions)}})
    path=FIX/f"{dist}.csv";csvwrite(path,fields,rows); data=path.read_bytes(); digest=hashlib.sha256(data).hexdigest()
    snaps.append({"source_id":f"indec_{measure.lower()}_regional_monthly","dataset_id":dist.split('.')[0],"distribution_id":dist,"dataset_page":"fixture://dataset","requested_url":"fixture://csv","resolved_url":"fixture://csv","retrieved_at_utc":"2026-08-04T00:00:00Z","byte_size":len(data),"sha256":digest,"http_headers":{"content-type":"text/csv"},"parser_id":"datos-gob-ar-regional-wide-csv/v1","actual_schema":fields,"period_start":"2016-01-01","period_end":"2024-03-01","row_count":24,"publisher":"fixture only","publisher_catalog":"fixture only","license":"fixture only","unit_metadata":"deliberately unresolved fixture wording","cache_file":str(path.relative_to(ROOT))})
(FIX/"source_lock.json").write_text(json.dumps({"schema":"regional-basket-source-lock/v1","snapshots":snaps},indent=2,sort_keys=True)+"\n")
price=FIX/"price_release";price.mkdir(exist_ok=True)
csvwrite(price/"monthly_prices.csv",["period","price_index","value_status"],[{"period":"2016-01-01","price_index":"100","value_status":"observed"},{"period":"2024-01-01","price_index":"400","value_status":"observed"},{"period":"2024-02-01","price_index":"410","value_status":"observed"},{"period":"2024-03-01","price_index":"420","value_status":"observed"}])
p=price/"monthly_prices.csv"; manifest={"schema":"research-artifact-manifest/v1","artifact_type":"research.argentina-price-composite/v1","release_id":"fixture-price-candidate-v1","status":"candidate","method_id":"research.argentina-price-composite/legacy-compatible-v1","monetary_reference_id":"research.argentina-price-composite/legacy-compatible-v1@2016-01=100","warnings":["fixture provenance warning"],"files":{"monthly_prices.csv":{"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}}};(price/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
print(FIX)
