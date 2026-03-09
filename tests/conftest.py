import os
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.config.settings import get_settings
from app.infrastructure.db.models import Base


@pytest.fixture(autouse=True)
def test_env(tmp_path: Path) -> Generator[None, None, None]:
    db_path = tmp_path / "daemon_test.db"
    os.environ["USE_SQLITE"] = "true"
    os.environ["SQLITE_DATABASE_URL"] = f"sqlite+pysqlite:///{db_path.as_posix()}"
    os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
    os.environ["LOG_ECS_ENABLED"] = "false"
    get_settings.cache_clear()

    settings = get_settings()
    engine = create_engine(
        settings.effective_database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()
    get_settings.cache_clear()
