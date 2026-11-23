import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.models.entities import Base
from scripts.seed import seed


@pytest.fixture
def session(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setenv("RAW_DIR", str(tmp_path / "archive"))
    settings.cache_clear()
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"core": None, "regional": None}},
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed(session, external=False)
        session.commit()
        yield session
    engine.dispose()
    settings.cache_clear()
