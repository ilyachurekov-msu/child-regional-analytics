from fastapi.testclient import TestClient
from app.api.main import app
from app.db import get_session
from app.services.analytics import change, construct_index
from app.services.export import export_rows
from tests.test_etl import write, URL
from app.etl.importer import import_file


def test_api(session, tmp_path):
    def override():
        yield session

    app.dependency_overrides[get_session] = override
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/regions", params={"limit": 2})
            assert response.status_code == 200
            assert response.json()["total"] == 85
            assert len(response.json()["items"]) == 2
            assert client.get("/api/v1/regions/unknown").status_code == 404
            invalid = client.get("/api/v1/regional/values?limit=0")
            assert invalid.status_code == 422 and "error" in invalid.json()
            assert (
                client.get(
                    "/api/v1/regional/comparison?region_ids=RU-77&indicator_code=births"
                ).status_code
                == 422
            )
            path = tmp_path / "values.csv"
            write(path, ["100", "110"])
            import_file(session, path, URL, "Test fixture")
            values = client.get("/api/v1/regional/values?region_id=RU-77").json()
            assert values["total"] == 2
            assert values["items"][0]["source_url"] == URL
            assert (
                len(
                    client.get("/api/v1/regional/profiles/RU-77").json()["observations"]
                )
                == 2
            )
            comparison = client.get(
                "/api/v1/regional/comparison",
                params=[
                    ("region_ids", "RU-77"),
                    ("region_ids", "RU-78"),
                    ("indicator_code", "births"),
                ],
            ).json()
            assert float(comparison["changes"]["RU-77"]["absolute_change"]) == 10
            assert (
                client.get("/api/v1/regional/export?format=xlsx").content[:2] == b"PK"
            )
            assert b"source_url" in client.get("/api/v1/regional/export").content
            assert (
                client.get("/api/v1/regional/data-quality").json()[
                    "current_observations"
                ]
                == 2
            )
            assert (
                "/api/v1/regions" in client.get("/api/v1/openapi.json").json()["paths"]
            )
    finally:
        app.dependency_overrides.clear()


def test_analysis_and_safe_export():
    assert change(0, 10)["relative_change_percent"] is None
    assert change(None, 10)["absolute_change"] is None
    assert b"'=CMD" in export_rows([{"name": "=CMD"}], "csv")
    result = construct_index(
        {"a": {"x": 1}, "b": {"x": 3}, "c": {"x": None}}, {"x": 1}, {"x": "negative"}
    )
    assert result == {"a": 100, "b": 0, "c": None}
