"""Database engine, session factory, declarative base."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core import settings

if settings.testing:
    engine = create_engine("sqlite:///:memory:", echo=False)
else:
    engine = create_engine(settings.database_url, echo=False, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():  # type: ignore[return]
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
