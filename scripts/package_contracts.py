"""Explicit contract release preparation, never an implicit CI mutation."""

import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL


def main():
    root = Path("shared-contracts/src/navigator_shared_contracts")
    root.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name in ("regions.csv", "topics.json", "platform.schema.json"):
        payload = Path("contracts", name).read_bytes().replace(b"\r\n", b"\n")
        (root / name).write_bytes(payload)
        hashes[name] = hashlib.sha256(payload).hexdigest()
    manifest = {
        "version": "1.0.0",
        "platform_agreed": False,
        "status": "candidate, regional IDs retained pending cross-module reconciliation",
        "source_uuid_namespace": str(NAMESPACE_URL),
        "resources_sha256": hashes,
        "other_modules": {
            "media": "incompatible IDs and source namespace",
            "practices": "not available for comparison",
        },
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
