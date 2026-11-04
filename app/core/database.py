from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from app.core.config import settings

# 1. Database engine
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    # echo=True,  # Enable to inspect SQL queries during development
)

# 2. Session factory (standard PascalCase naming)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
sessionlocal = SessionLocal  # Backward-compatible alias


# 3. Declarative Base for models
class Base(DeclarativeBase):
    pass


# 4. FastAPI dependency for DB sessions
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
