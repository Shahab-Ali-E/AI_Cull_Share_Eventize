from sqlalchemy.orm import declarative_base
from config.settings import get_settings
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncConnection, async_sessionmaker
from typing import AsyncGenerator, AsyncIterator, Any
from contextlib import asynccontextmanager

settings = get_settings()

Base = declarative_base()

class DatabaseSessionManager:
    def __init__(self, host: str, engine_kwargs: dict[str, Any] = {}):
        self._engine = create_async_engine(host, **engine_kwargs)
        self._sessionmaker = async_sessionmaker(bind=self._engine, expire_on_commit=False, class_=AsyncSession, autoflush=True, autocommit=False)
    
    async def close(self):
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")

        await self._engine.dispose()
        self._engine = None
        self._sessionmaker = None
    
    @asynccontextmanager
    async def connect(self) -> AsyncIterator[AsyncConnection]:
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")
        
        async with self._engine.connect() as connection:
            try:
                yield connection
            except Exception:
                await connection.rollback()
                raise
    
    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._sessionmaker is None:
            raise Exception("DatabaseSessionManager is not initialized")

        async with self._sessionmaker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

sessionmanager = DatabaseSessionManager(host=settings.DATABASE_URI, 
                                        engine_kwargs={"echo":True,            # The echo parameter is used to enable SQL query logging
                                                        "pool_pre_ping": False,
                                                        "pool_recycle": 3600,  # Recycles connections after 1 hour
                                                        "pool_size": 100,       # Number of connections to keep in the pool
                                                        "max_overflow": 0     # Allows up to 10 additional connections beyond pool_size
                                                    }
                                        )

async def get_db():
    async with sessionmanager.session() as session:
        yield session
