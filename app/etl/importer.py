"""Transactional normalized-file loader. No network or fabricated observations."""

import csv
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from sqlalchemy import select, text
from app.config import settings
from app.etl.normalize import normalize_region, number, source_identifier
from app.models.entities import Batch, Indicator, QualityIssue, Region, Source, Value

PARSER_VERSION = "1.0.0"
FIELDS = {
    "indicator_code",
    "region",
    "period_start",
    "period_end",
    "value",
    "published_at",
}


def read_rows(path):
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            return list(
                csv.DictReader(
                    handle, dialect=csv.Sniffer().sniff(sample, delimiters=",;\t")
                )
            )
    if suffix == ".xlsx":
        from openpyxl import load_workbook

        book = load_workbook(path, read_only=True, data_only=True)
        try:
            rows = iter(book.active.values)
            header = next(rows)
            return [
                dict(zip(header, row))
                for row in rows
                if any(v is not None for v in row)
            ]
        finally:
            book.close()
    if suffix == ".json":
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise ValueError("JSON должен содержать массив объектов")
        return rows
    raise ValueError("Поддерживаются CSV, XLSX, JSON")


def import_file(session, path, source_url, source_name, publisher="Росстат"):
    path = Path(path)
    payload = path.read_bytes()
    if len(payload) > 50 * 1024 * 1024:
        raise ValueError("Файл превышает 50 МБ")
    checksum = hashlib.sha256(payload).hexdigest()
    identifier = source_identifier(source_url)
    if session.bind.dialect.name == "postgresql":
        # Serialize revisions and source registration across all importer workers.
        session.execute(text("SELECT pg_advisory_xact_lock(1701202601)"))
    source = session.scalar(
        select(Source).where(Source.normalized_identifier == identifier)
    )
    if source is None:
        source = Source(
            source_id=uuid5(NAMESPACE_URL, identifier),
            normalized_identifier=identifier,
            source_type="official_statistics",
            name=source_name,
            url=source_url,
            publisher=publisher,
        )
        session.add(source)
        session.flush()
    previous = session.scalar(
        select(Batch).where(
            Batch.source_id == source.source_id,
            Batch.checksum == checksum,
            Batch.parser_version == PARSER_VERSION,
        )
    )
    if previous:
        return previous
    directory = Path(settings().raw_dir)
    directory.mkdir(parents=True, exist_ok=True)
    archived = directory / (checksum + path.suffix.lower())
    if not archived.exists():
        archived.write_bytes(payload)
    batch = Batch(
        source_id=source.source_id,
        checksum=checksum,
        raw_path=str(archived),
        parser_version=PARSER_VERSION,
    )
    session.add(batch)
    session.flush()
    regions = session.scalars(select(Region)).all()
    mapping = {}
    for region in regions:
        for key in (region.region_id, normalize_region(region.name)):
            mapping.setdefault(key, []).append(region)
    alias_path = Path("contracts/region_aliases.json")
    aliases = (
        json.loads(alias_path.read_text(encoding="utf-8"))
        if alias_path.exists()
        else {}
    )
    indicators = {i.code: i for i in session.scalars(select(Indicator)).all()}
    batch.rows_processed = batch.errors = 0
    try:
        rows = read_rows(path)
    except Exception as exc:
        session.add(
            QualityIssue(
                batch_id=batch.batch_id, issue_type="format", description=str(exc)
            )
        )
        batch.status, batch.errors = "failed", 1
        session.flush()
        return batch
    seen = set()
    for line, row in enumerate(rows, start=2):
        indicator = region = None
        batch.rows_processed += 1
        try:
            if not FIELDS.issubset(row):
                raise ValueError("Отсутствуют обязательные столбцы")
            indicator = indicators.get(row["indicator_code"])
            if not indicator or not indicator.is_active:
                raise ValueError("Неизвестный или неактивный показатель")
            raw_region = str(row["region"])
            key = raw_region if raw_region in mapping else normalize_region(raw_region)
            key = aliases.get(key, key)
            matches = mapping.get(key, [])
            if len(matches) != 1:
                raise ValueError("Неоднозначный или неизвестный регион: " + raw_region)
            region = matches[0]
            start = date.fromisoformat(str(row["period_start"])[:10])
            end = date.fromisoformat(str(row["period_end"])[:10])
            if (
                end < start
                or start < region.valid_from
                or (region.valid_to and end > region.valid_to)
            ):
                raise ValueError("Период вне границ действия региона")
            if start != date(start.year, 1, 1) or end != date(start.year, 12, 31):
                raise ValueError(
                    "Начальные показатели допускают только полный календарный год"
                )
            published = datetime.fromisoformat(
                str(row["published_at"]).replace("Z", "+00:00")
            )
            if published.tzinfo is None:
                raise ValueError("published_at должен содержать часовой пояс")
            value = number(row["value"])
            if value is not None and value < 0 and indicator.code != "natural_change":
                raise ValueError("Отрицательное значение недопустимо")
            key = (indicator.indicator_id, region.region_id, start, end)
            if key in seen:
                raise ValueError("Повтор наблюдения внутри файла")
            seen.add(key)
            old = session.scalar(
                select(Value).where(
                    Value.indicator_id == key[0],
                    Value.region_id == key[1],
                    Value.period_start == start,
                    Value.period_end == end,
                    Value.is_current.is_(True),
                )
            )
            if old and old.value == value and old.source_id == source.source_id:
                continue
            if old:
                old_published = old.published_at
                if old_published.tzinfo is None:
                    old_published = old_published.replace(tzinfo=timezone.utc)
                if published < old_published:
                    raise ValueError("Публикация старее текущей версии")
            revision = old.revision_number + 1 if old else 1
            if old:
                old.is_current = False
                session.flush()
            session.add(
                Value(
                    indicator_id=key[0],
                    region_id=key[1],
                    period_start=start,
                    period_end=end,
                    value=value,
                    source_id=source.source_id,
                    batch_id=batch.batch_id,
                    published_at=published.astimezone(timezone.utc),
                    data_status="missing" if value is None else "official",
                    revision_number=revision,
                )
            )
            session.flush()
            if value is None:
                session.add(
                    QualityIssue(
                        batch_id=batch.batch_id,
                        indicator_id=key[0],
                        region_id=key[1],
                        issue_type="missing",
                        description=f"Строка {line}: значение отсутствует",
                    )
                )
        except (ValueError, TypeError) as exc:
            batch.errors += 1
            session.add(
                QualityIssue(
                    batch_id=batch.batch_id,
                    indicator_id=indicator.indicator_id if indicator else None,
                    region_id=region.region_id if region else None,
                    issue_type="region_mapping"
                    if "регион" in str(exc)
                    else "validation",
                    description=f"Строка {line}: {exc}",
                )
            )
    batch.status = "completed_with_errors" if batch.errors else "completed"
    session.flush()
    return batch
