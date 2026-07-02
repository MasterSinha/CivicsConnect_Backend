from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


settings = get_settings()


def normalize_database_url(database_url: str) -> str:
    # SQLAlchemy 1.4+ requires 'postgresql://' instead of 'postgres://'
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    # Ensure psycopg2 driver is used (sync connection required by SQLAlchemy create_engine)
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if database_url.startswith("postgresql://") and "+psycopg2" not in database_url:
        return database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return database_url


engine = create_engine(normalize_database_url(settings.database_url), pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

