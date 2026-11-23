import json
from pathlib import Path
from sqlalchemy import func, select
from app.etl.adapters import kemerovo_html
from app.models.entities import Value
from scripts.load_official_bundle import load_bundle


def test_official_bundle_values_and_idempotence(session):
    first = load_bundle(session)
    assert (
        first.original_checksum
        == "b3d8aba8e051d2ed98878258c950356f7b16d8680b73e1ff184452cac47078b3"
    )
    assert load_bundle(session).batch_id == first.batch_id
    assert session.scalar(select(func.count()).select_from(Value)) == 20
    rows = json.loads(
        Path("data/official/kemerovo-2022.json").read_text(encoding="utf-8")
    )
    assert (
        next(
            r
            for r in rows
            if r["period_start"] == "2022-01-01" and r["indicator_code"] == "births"
        )["value"]
        == "19765"
    )
    assert (
        next(
            r
            for r in rows
            if r["period_start"] == "2022-01-01"
            and r["indicator_code"] == "natural_change"
        )["value"]
        == "-18600"
    )


def test_html_parser_and_fail_closed():
    import pytest

    # Entirely synthetic layout: no internet, original publication not redistributed.
    demo = "<table><tr><td>Годы</td><td>Всего, человек</td></tr><tr><td>родившихся</td></tr><tr><td>header</td></tr><tr><td>Всё население</td></tr>"
    for year in range(2018, 2023):
        demo += (
            "<tr>"
            + "".join(
                "<td>" + str(v) + "</td>"
                for v in [year, 10, 15, -5, 1, 2, 3, 4, 5, 6, ""]
            )
            + "</tr>"
        )
    demo += "</table>"
    marriage = (
        "<table><tr>"
        + "".join("<td>" + str(v) + "</td>" for v in ["", 2018, 2019, 2020, 2021, 2022])
        + "</tr><tr></tr><tr>"
        + "".join("<td>" + str(v) + "</td>" for v in ["Браков", 1, 2, 3, 4, 5])
        + "</tr><tr>"
        + "".join("<td>" + str(v) + "</td>" for v in ["Разводов", 1, 2, 3, 4, 5])
        + "</tr><tr><td>На 1000 жителей</td></tr></table>"
    )
    html = (
        "<meta charset=windows-1251><p>4.12. РОЖДАЕМОСТЬ, СМЕРТНОСТЬ И ЕСТЕСТВЕННЫЙ ПРИРОСТ НАСЕЛЕНИЯ</p>"
        + demo
        + "<p>4.20. БРАКИ И РАЗВОДЫ</p>"
        + marriage
    )
    spec = {"region_id": "RU-42", "years": [2019, 2020, 2021, 2022]}
    assert len(kemerovo_html(html.encode("cp1251"), spec)) == 20
    with pytest.raises(ValueError):
        kemerovo_html(
            html.replace("Всего, человек", "На 1000 жителей").encode("cp1251"), spec
        )


def test_metadata_tracks_database_load(session):
    from fastapi.testclient import TestClient
    from app.api.main import app
    from app.db import get_session

    load_bundle(session)
    app.dependency_overrides[get_session] = lambda: session
    try:
        with TestClient(app) as client:
            cards = client.get("/api/v1/regional/indicator-metadata").json()["items"]
            assert len(cards) == 5
            assert all(
                card["observations_loaded"] == 4 and card["last_successful_load"]
                for card in cards
            )
    finally:
        app.dependency_overrides.clear()
