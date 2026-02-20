"""
@description 异步数据库连接管理
@responsibility 提供 SQLAlchemy 异步引擎、会话管理和数据库初始化
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import asynccontextmanager

DATABASE_URL = "sqlite+aiosqlite:///./db/data.db"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

async_session_local = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def init_db():
    """
    初始化数据库，创建所有表
    """
    # 导入所有模型，确保在 Base.metadata 中注册
    from app.models.offline_task import OfflineTask
    from app.models.organize_record import OrganizeRecord
    from app.models.path_id_cache import PathIdCache

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session():
    """
    异步会话上下文管理器
    """
    async with async_session_local() as session:
        try:
            yield session
        finally:
            await session.close()
