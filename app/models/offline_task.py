"""
@description 离线任务历史记录模型
@responsibility 记录离线下载任务的完整生命周期
"""

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from datetime import datetime
from app.core.database import Base


class OfflineTask(Base):
    __tablename__ = "offline_task"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # BT 任务的 info_hash（40 位 hex），可能为 NULL
    # - API 不稳定，可能不总是返回
    # - magnet 链接可能格式异常，解析失败
    # - 允许先创建任务，后续补齐 info_hash
    # 移除 unique 约束：SQLite 中多个 NULL 会违反约束
    # 保持非唯一索引提高查询性能
    info_hash = Column(String(64), nullable=True, unique=True)
    name = Column(String(512))
    library_name = Column(String(255))
    status = Column(String(50))
    add_time = Column(DateTime)
    complete_time = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
