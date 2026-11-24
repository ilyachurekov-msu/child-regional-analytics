"""Extract the additional observed year from the previously verified original."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from app.etl.adapters import kemerovo_html


def main():
    meta = json.loads(Path("data/official/provenance.json").read_text(encoding="utf-8"))
    raw = Path("data/raw/kemerovo-2022.html").read_bytes()
    if hashlib.sha256(raw).hexdigest() != meta["source_sha256"]:
        raise ValueError("Original differs from inspected edition")
    rows = kemerovo_html(raw, {"region_id": "RU-42", "years": list(range(2018, 2023))})
    path = Path("data/official/kemerovo-2018-2022.json")
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8", newline='\n')
    meta.update(
        observations=len(rows),
        years=list(range(2018, 2023)),
        normalized_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        normalized_file=path.name,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        adapter="kemerovo-yearbook-html/1.1.0",
        comparability="Annual whole-population absolute ZAGS counts; rates and urban/rural groups excluded",
    )
    Path("data/official/provenance-v02.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        "Verified observed values:",
        len(rows),
        "; 2018:",
        [r for r in rows if r["period_start"].startswith("2018")],
    )


if __name__ == "__main__":
    main()
