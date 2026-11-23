import csv
import json
from datetime import date
from pathlib import Path
from uuid import UUID
from sqlalchemy.orm import Session
from app.config import settings
from app.db import engine
from app.models.entities import Indicator, Region, Topic


def seed(session, external=None):
    external = settings().core_managed_externally if external is None else external
    if not external:
        with Path("contracts/regions.csv").open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                for key in ("valid_from", "valid_to"):
                    row[key] = date.fromisoformat(row[key]) if row[key] else None
                for key in ("okato_code", "oktmo_code"):
                    row[key] = row[key] or None
                if not session.get(Region, row["region_id"]):
                    session.add(Region(**row))
        for row in json.loads(
            Path("contracts/topics.json").read_text(encoding="utf-8")
        ):
            if not session.get(Topic, row["topic_id"]):
                session.add(Topic(**row))
        session.flush()
    for row in json.loads(
        Path("contracts/indicators.json").read_text(encoding="utf-8")
    ):
        row["indicator_id"] = UUID(row["indicator_id"])
        if not session.get(Indicator, row["indicator_id"]):
            session.add(Indicator(**row))
    session.flush()


if __name__ == "__main__":
    with Session(engine()) as session, session.begin():
        seed(session)
