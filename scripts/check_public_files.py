"""Small local pre-publication guard; CI additionally runs Gitleaks on history."""

import re
import subprocess
from pathlib import Path

PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{40,}"),
    re.compile(r"AKIA[A-Z0-9]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def main():
    paths = subprocess.check_output(["git", "ls-files", "-z"], text=True).split("\0")
    failures = []
    for name in filter(None, paths):
        path = Path(name)
        if name == ".env" or name.startswith(
            (
                ".deps/",
                ".venv/",
                "child-media-monitor/",
                "child-practices-search/",
                "data/archive/",
            )
        ):
            failures.append(name + ": prohibited public path")
            continue
        if path.suffix.lower() in (".pdf", ".xlsx"):
            failures.append(name + ": unreviewed raw binary data")
            continue
        payload = path.read_text(encoding="utf-8", errors="replace")
        if any(pattern.search(payload) for pattern in PATTERNS):
            failures.append(name + ": potential secret (value redacted)")
    if failures:
        raise SystemExit("\n".join(failures))
    print(
        f"Public-file guard passed for {len(list(filter(None, paths)))} tracked paths; no secret values printed"
    )


if __name__ == "__main__":
    main()
