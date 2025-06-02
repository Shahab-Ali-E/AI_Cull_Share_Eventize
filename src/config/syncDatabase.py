from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from src.config.settings import get_settings
from typing import Iterator

settings = get_settings()
# Create a default SSL context or pass True/"require" per your needs
# ssl_context = create_default_context()

# Create synchronous engine for Celery
sync_engine = create_engine(
    settings.SYNC_DATABASE_URI,
    echo=True,
    # connect_args={"ssl": ssl_context},
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=10,        
    max_overflow=5
)

# Set up synchronous session for Celery tasks
SyncSessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)

@contextmanager
def celery_sync_session() -> Iterator[sessionmaker]:
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
