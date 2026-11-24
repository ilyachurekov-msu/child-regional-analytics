"""Optional local scheduler. Disabled by default; never stores a database in CI."""

import os
import subprocess
import sys
import time
import json
from pathlib import Path


def main():
    if os.getenv("STAT_UPDATES_ENABLED", "false").lower() != "true":
        print("Statistical update scheduler disabled")
        return
    interval = max(3600, int(os.getenv("STAT_UPDATE_INTERVAL", "86400")))
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
