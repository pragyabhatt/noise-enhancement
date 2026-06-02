from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.db.models import Base

# Setup async engine for SQLite (using aiosqlite)
engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=False,
    connect_args={"check_same_thread": False} # Required for SQLite multi-thread access
)

AsyncSessionLocal = sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

async def get_db():
    """
    Dependency helper to acquire a database session and close it automatically.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    """
    Initialize database schema (creates tables if they do not exist).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
