from sqlalchemy.orm import sessionmaker,declarative_base
from sqlalchemy import create_engine
from config.settings import get_settings
from typing import Generator

settings = get_settings()

engine = create_engine(settings.DATABASE_URI,
                       pool_pre_ping=True,
                       pool_recycle=3600,
                       pool_size=20,
                       max_overflow=10
                       )

session = sessionmaker(autoflush=False, autocommit=False, bind=engine)

Base = declarative_base()

# Dependency
def get_db() -> Generator:
    db = session()
    try:
        yield db
    finally:
        db.close()