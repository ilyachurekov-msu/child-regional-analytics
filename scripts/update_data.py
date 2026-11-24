"""Controlled update: explicit manifest source, optional local official original."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import httpx
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.db import engine
from app.etl.adapters import adapt_pdf, kemerovo_html
from app.etl.importer import import_file
from app.etl.comparability import validate_series


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument(
        "--file", type=Path, help="Original official PDF obtained lawfully"
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument('--dry-run', action='store_true', help='Validate without database writes')
    parser.add_argument(
        "--approve-adapter",
        action="store_true",
        help="Explicit one-off approval after verifying original and adapter output",
    )
    args = parser.parse_args()
    manifest = json.loads(Path("data/source-manifest.json").read_text(encoding="utf-8"))
    source = next((s for s in manifest["sources"] if s["id"] == args.source), None)
    if not source:
        raise SystemExit("Unknown manifest source")
    folder = Path("data/archive")
    folder.mkdir(parents=True, exist_ok=True)
    report = {
        'run_id': str(uuid4()),
        "source": source["id"],
        "url": source["url"],
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "started",
    }
    try:
        if args.file:
            original = args.file.read_bytes()
        else:
            # TLS remains verified. No CAPTCHA, alternate-host or access-control bypass.
            with httpx.Client(timeout=30, follow_redirects=False) as client:
                response = client.get(source["url"])
                response.raise_for_status()
                original = response.content
        is_html = source["format"] == "html"
        if (not is_html and not original.startswith(b"%PDF-")) or len(
            original
        ) > 50 * 1024 * 1024:
            raise ValueError("Unexpected original format or size exceeds 50MB")
        checksum = hashlib.sha256(original).hexdigest()
        state_path = Path('data/load-state.json')
        state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
        previous = state.get(source['id'], {})
        report['changed'] = previous.get('sha256') != checksum
        if not report['changed'] and previous.get('adapter') == source['adapter'] and not (args.validate_only or args.dry_run):
            report.update(status='unchanged', sha256=checksum)
            return
        path = folder / (checksum + (".html" if is_html else ".pdf"))
        if not path.exists():
            path.write_bytes(original)
        rows = (
            kemerovo_html(original, source)
            if is_html and source["adapter"] in ('kemerovo-yearbook-html/1.0.0', 'kemerovo-yearbook-html/1.1.0')
            else adapt_pdf(path, source)
        )
        validate_series(rows, source)
        normalized = folder / (checksum + ".normalized.json")
        normalized.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        report.update(
            sha256=checksum,
            rows=len(rows),
            status="validated",
            normalized=str(normalized),
            preview=rows,
        )
        if not (args.validate_only or args.dry_run):
            if not source["enabled"] and not args.approve_adapter:
                raise ValueError(
                    "Adapter pending original-file review: run --validate-only, compare with original, then explicitly --approve-adapter"
                )
            with Session(engine()) as session, session.begin():
                batch = import_file(
                    session,
                    normalized,
                    source["url"],
                    source["name"],
                    source["publisher"],
                    original_path=path,
                    parser_version=source["adapter"],
                )
                report.update(
                    batch_id=str(batch.batch_id),
                    errors=batch.errors,
                    status=batch.status,
                )
                if batch.errors or batch.status == "failed":
                    raise ValueError("Import contains quality issues; transaction rolled back")
            state_path = Path("data/load-state.json")
            state = (
                json.loads(state_path.read_text(encoding="utf-8"))
                if state_path.exists()
                else {}
            )
            state[source["id"]] = dict(
                last_successful_load=datetime.now(timezone.utc).isoformat(),
                sha256=checksum,
                observations=len(rows),
                years=source["years"],
                region_id=source["region_id"],
                adapter=source['adapter'],
            )
            state_path.write_text(
                json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    except (httpx.HTTPError, ValueError, OSError, SQLAlchemyError) as exc:
        report.update(status="failed", error=str(exc) if isinstance(exc, ValueError) else type(exc).__name__)
    finally:
        report_path = folder / "latest-update-report.json"
        (folder / ('update-' + report['run_id'] + '.json')).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
