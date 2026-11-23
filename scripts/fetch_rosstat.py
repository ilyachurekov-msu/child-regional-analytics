"""Download only links discovered on the official source page; verify TLS and format."""

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import httpx

PAGE = "https://rosstat.gov.ru/compendium/document/13269"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/raw")
    args = parser.parse_args()
    folder = Path(args.output)
    folder.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        response = client.get(PAGE)
        response.raise_for_status()
        (folder / "source_page.html").write_text(response.text, encoding="utf-8")
        links = list(
            dict.fromkeys(
                re.findall(
                    r"href=[\"\x27]([^\"\x27]+\.xlsx)[\"\x27]", response.text, re.I
                )
            )
        )
        if not links:
            raise RuntimeError(
                "На странице нет XLSX. Требуется ручная проверка публикации."
            )
        report = []
        for link in links:
            url = urljoin(PAGE, link)
            if urlsplit(url).hostname not in ("rosstat.gov.ru", "www.rosstat.gov.ru"):
                continue
            item = {"url": url, "checked_at": datetime.now(timezone.utc).isoformat()}
            try:
                response = client.get(url)
                response.raise_for_status()
                if not response.content.startswith(b"PK"):
                    raise ValueError("Ответ не является XLSX")
                path = folder / Path(urlsplit(url).path).name
                path.write_bytes(response.content)
                item.update(
                    status="downloaded",
                    sha256=hashlib.sha256(response.content).hexdigest(),
                )
            except (httpx.HTTPError, ValueError) as exc:
                item.update(status="unavailable", error=str(exc))
            report.append(item)
            time.sleep(1)
        (folder / "download_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not any(r["status"] == "downloaded" for r in report):
            raise SystemExit(
                "Ни один файл недоступен. Используйте ручной импорт; данные не созданы."
            )


if __name__ == "__main__":
    main()
