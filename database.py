"""数据库配置和初始化模块"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base

# 数据库引擎配置
DATABASE_URL = "sqlite+aiosqlite:///./media.db"

# 创建异步引擎
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # 设置为 True 可以查看 SQL 语句
    connect_args={"check_same_thread": False},
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# 声明基类
Base = declarative_base()


async def get_db():
    """
    FastAPI 依赖函数，用于获取数据库会话
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """
    初始化数据库，创建所有表；并对已有表执行增量列迁移
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 增量迁移：为旧数据库补充 preview_path 列（若已存在则跳过）
        await conn.run_sync(_migrate_add_preview_path)


def _migrate_add_preview_path(sync_conn):
    """同步函数：检查并添加 preview_path 列（供 run_sync 调用）"""
    import sqlalchemy as sa
    inspector = sa.inspect(sync_conn)
    existing_cols = {col["name"] for col in inspector.get_columns("media")}
    if "preview_path" not in existing_cols:
        sync_conn.execute(sa.text("ALTER TABLE media ADD COLUMN preview_path VARCHAR(512)"))



async def close_db():
    """
    关闭数据库连接
    """
    await engine.dispose()
