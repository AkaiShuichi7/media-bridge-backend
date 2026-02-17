"""
@description 路径 ID 缓存模型
@responsibility 缓存路径到目录 ID 的映射关系，支持 TTL 清理和访问统计
"""

from sqlalchemy import Column, Integer, String, Index, UniqueConstraint
from app.core.database import Base


class PathIdCache(Base):
    __tablename__ = "path_id_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    library_name = Column(String(255), nullable=False)
    path = Column(String(1024), nullable=False)
    path_id = Column(Integer, nullable=False)
    expires_at = Column(Integer, nullable=False)
    last_access_at = Column(Integer, nullable=True)
    hit_count = Column(Integer, default=0, nullable=False)
    created_at = Column(Integer, nullable=False)
    updated_at = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("library_name", "path", name="uq_library_path"),
        Index("ix_path_id_cache_expires_at", "expires_at"),
        Index("ix_path_id_cache_library_expires", "library_name", "expires_at"),
    )
