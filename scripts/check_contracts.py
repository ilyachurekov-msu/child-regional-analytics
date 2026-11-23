import csv
import hashlib
import json
from pathlib import Path
from uuid import UUID


def main():
    root = Path("shared-contracts/src/navigator_shared_contracts")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "1.0.0"
    for name, expected in manifest["resources_sha256"].items():
        original = Path("contracts", name).read_bytes().replace(b"\r\n", b"\n")
        packaged = (root / name).read_bytes().replace(b"\r\n", b"\n")
        assert original == packaged, "Contract package drift: " + name
        assert hashlib.sha256(packaged).hexdigest() == expected, (
            "Unexpected contract mutation: " + name
        )
    with Path("contracts/regions.csv").open(encoding="utf-8", newline="") as handle:
        regions = list(csv.DictReader(handle))
    assert len({r["region_id"] for r in regions}) == len(regions)
    region_ids = {r["region_id"] for r in regions}
    assert {"RU", "RU-77", "RU-78", "FD-01"} <= region_ids
    topics = json.loads(Path("contracts/topics.json").read_text(encoding="utf-8"))
    codes = {t["topic_id"] for t in topics}
    assert codes == {
        "demography",
        "family",
        "education",
        "healthcare",
        "social_support",
        "orphanhood",
        "safety",
        "infrastructure",
    }
    indicators = json.loads(
        Path("contracts/indicators.json").read_text(encoding="utf-8")
    )
    for row in indicators:
        UUID(row["indicator_id"])
        assert row["topic_id"] in codes
    assert not manifest["platform_agreed"], (
        "Do not assert agreement without all three modules"
    )
    print(
        "Contract package integrity passed; platform compatibility remains explicitly unconfirmed"
    )


if __name__ == "__main__":
    main()
