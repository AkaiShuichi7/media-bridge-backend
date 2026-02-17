"""
@description 整理记录数据模型
@responsibility 记录文件整理操作的完整信息
"""

from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Text
from sqlalchemy.sql import func
from datetime import datetime
from app.core.database import Base


class OrganizeRecord(Base):
    __tablename__ = "organize_record"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(255), index=True)
    source_path = Column(String(1024))
    target_path = Column(String(1024))
    file_name = Column(String(512))
    file_size = Column(BigInteger)
    library_name = Column(String(255))
    status = Column(String(50))
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
