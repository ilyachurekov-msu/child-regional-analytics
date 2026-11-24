from pathlib import Path
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest
from app.api.main import app
from app.db import get_session
from app.etl.importer import import_file
from tests.test_etl import write, URL
import pytest


@pytest.mark.parametrize("with_values", [False, True])
def test_all_ui_pages(session, monkeypatch, tmp_path, with_values):
    if with_values:
        fixture_file = tmp_path / "ui-fixture.csv"
        write(fixture_file, ["100", "110", "120"])
        import_file(session, fixture_file, URL, "Test fixture")

    def override():
        yield session

    app.dependency_overrides[get_session] = override
    try:
        with TestClient(app) as client:

            def api_get(url, params=None, **kwargs):
                route = "/api/v1/" + url.split("/api/v1/", 1)[1]
                return client.get(route, params=params)

            monkeypatch.setattr("httpx.get", api_get)
            ui = AppTest.from_file(
                Path("app/ui/main.py").resolve(), default_timeout=30
            ).run()
            assert not ui.exception
            pages = [
                "Карта России",
                "Паспорт региона",
                "Сравнение регионов",
                "Динамика показателей",
                "Качество и актуальность данных",
                "Экспорт аналитической справки",
            ]
            for page in pages:
                ui.sidebar.radio[0].set_value(page).run()
                assert not ui.exception, (page, ui.exception)
                if page == "Карта России":
                    next(s for s in ui.selectbox if s.label == "Профиль региона на карте").set_value("RU-42").run()
                    next(b for b in ui.button if b.label == "Открыть профиль региона").click().run()
                    assert not ui.exception
                    assert ui.sidebar.radio[0].value == "Паспорт региона"
                    assert ui.session_state["profile_region"] == "RU-42"
                if with_values and page in (
                    "Паспорт региона",
                    "Динамика показателей",
                    "Экспорт аналитической справки",
                ):
                    ui.selectbox[0].set_value("RU-77").run()
                    assert not ui.exception, (page, ui.exception)
                if with_values and page == "Сравнение регионов":
                    ui.multiselect[0].set_value(["RU-77", "RU-78"]).run()
                    assert not ui.exception
    finally:
        app.dependency_overrides.clear()

