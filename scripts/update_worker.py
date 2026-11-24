"""Optional local scheduler. Disabled by default; never stores a database in CI."""

import subprocess
import sys
import time
import json
from pathlib import Path
from app.config import settings


def main():
    if not settings().stat_updates_enabled:
        print("Statistical update scheduler disabled")
        return
    interval = max(3600, settings().stat_update_interval)
    while True:
        manifest = json.loads(
            Path("data/source-manifest.json").read_text(encoding="utf-8")
        )
        for source in manifest["sources"]:
            if source["enabled"]:
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "scripts.update_data",
                        "--source",
                        source["id"],
                    ],
                    check=False,
                )
        time.sleep(interval)


if __name__ == "__main__":
    main()
