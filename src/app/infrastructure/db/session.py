from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import Settings


def build_engine(settings: Settings):
    connect_args = {"check_same_thread": False} if settings.effective_database_url.startswith("sqlite") else {}
    return create_engine(settings.effective_database_url, future=True, pool_pre_ping=True, connect_args=connect_args)


def build_session_factory(settings: Settings):
    engine = build_engine(settings)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
