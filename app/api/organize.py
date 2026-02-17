"""
@description 整理记录查询接口
@responsibility 处理文件整理记录的查询操作
"""

from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import select, func

from app.core.database import get_session
from app.models.organize_record import OrganizeRecord
from app.schemas.api import OrganizeRecordItem, OrganizeRecordsResponse

router = APIRouter()


@router.get("/organize/records", response_model=OrganizeRecordsResponse)
async def get_organize_records(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="筛选状态"),
):
    async with get_session() as session:
        count_stmt = select(func.count()).select_from(OrganizeRecord)
        if status:
            count_stmt = count_stmt.where(OrganizeRecord.status == status)
        count_result = await session.execute(count_stmt)
        total = count_result.scalar()

        stmt = select(OrganizeRecord).order_by(OrganizeRecord.created_at.desc())
        if status:
            stmt = stmt.where(OrganizeRecord.status == status)
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await session.execute(stmt)
        records = result.scalars().all()

        record_items = [
            OrganizeRecordItem(
                id=record.id,
                file_name=record.file_name or "",
                source_path=record.source_path or "",
                target_path=record.target_path or "",
                status=record.status or "",
                created_at=record.created_at,
            )
            for record in records
        ]

        return OrganizeRecordsResponse(total=total, records=record_items)
