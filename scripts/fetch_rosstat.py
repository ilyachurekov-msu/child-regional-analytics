"""Download only links discovered on the official source page; verify TLS and format."""

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import httpx
from app.etl.official_http import OfficialHTTP

PAGE = "https://rosstat.gov.ru/compendium/document/13269"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/raw")
    args = parser.parse_args()
    folder = Path(args.output)
    folder.mkdir(parents=True, exist_ok=True)
    client = OfficialHTTP()
    try:
        page = client.get(PAGE, max_bytes=5 * 1024 * 1024)
    except (httpx.HTTPError, ValueError, OSError) as exc:
        report = dict(url=PAGE, checked_at=datetime.now(timezone.utc).isoformat(),
                      status="unavailable", error=type(exc).__name__)
        (folder / "download_report.json").write_text(json.dumps(report), encoding="utf-8")
        raise SystemExit("Официальная страница недоступна; отчет сохранен, повторов нет") from exc
    source_text = page.decode("utf-8-sig")
    (folder / "source_page.html").write_bytes(page)
    links = list(
        dict.fromkeys(
            re.findall(
                r"href=[\"\x27]([^\"\x27]+\.(?:xlsx?|zip))[\"\x27]", source_text, re.I
            )
        )
    )
    if not links:
        raise RuntimeError(
            "На странице нет XLS/XLSX/ZIP. Требуется проверка публикации."
        )
    report = []
    for link in links:
        url = urljoin(PAGE, link)
        if urlsplit(url).hostname not in ("rosstat.gov.ru", "www.rosstat.gov.ru"):
            continue
        item = {"url": url, "checked_at": datetime.now(timezone.utc).isoformat()}
        try:
            content = client.get(url)
            if not content.startswith((b"PK", bytes.fromhex("D0CF11E0A1B11AE1"))):
                raise ValueError("Ответ не является XLS/XLSX/ZIP")
            path = folder / Path(urlsplit(url).path).name
            path.write_bytes(content)
            item.update(
                status="downloaded",
                sha256=hashlib.sha256(content).hexdigest(),
            )
        except (httpx.HTTPError, ValueError) as exc:
            item.update(status="unavailable", error=str(exc))
        report.append(item)
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
