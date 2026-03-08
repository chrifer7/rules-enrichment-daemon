import os
from collections.abc import Generator
from pathlib import Path

import pytest

from app.config.settings import get_settings


@pytest.fixture(autouse=True)
def test_env(tmp_path: Path) -> Generator[None, None, None]:
    db_path = tmp_path / "daemon_test.db"
    os.environ["USE_SQLITE"] = "true"
    os.environ["SQLITE_DATABASE_URL"] = f"sqlite+pysqlite:///{db_path.as_posix()}"
    os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
    os.environ["LOG_ECS_ENABLED"] = "false"
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
