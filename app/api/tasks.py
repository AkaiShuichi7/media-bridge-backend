"""
@description 离线任务管理接口
@responsibility 处理离线任务的添加、查询、删除操作
"""

from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Depends
from loguru import logger
from sqlalchemy import select

from app.schemas.api import (
    AddTaskRequest,
    AddTaskResponse,
    TaskItem,
    TaskListResponse,
    TaskDetailResponse,
    DeleteTaskResponse,
    success_response,
)
from app.models.offline_task import OfflineTask
from app.core.database import get_session
from app.utils.helpers import parse_info_hash_from_magnet

if TYPE_CHECKING:
    from app.services.p115_client import P115Client
    from app.core.config import Config

router = APIRouter()

_p115_client: "P115Client" = None
_config: "Config" = None


def init_tasks_router(p115_client: "P115Client", config: "Config"):
    global _p115_client, _config
    _p115_client = p115_client
    _config = config


def _find_library_by_name(name: str):
    for library in _config.media.libraries:
        if library.name == name:
            return library
    return None


@router.post("/tasks")
async def add_task(request: AddTaskRequest):
    library = _find_library_by_name(request.library_name)
    if library is None:
        raise HTTPException(
            status_code=404, detail=f"媒体库 '{request.library_name}' 不存在"
        )

    # 先从 magnet 解析 info_hash 作为备用（API 可能不返回）
    parsed_info_hash = parse_info_hash_from_magnet(request.magnet)
    logger.info(f"从 magnet 解析 info_hash: {parsed_info_hash}")

    path_id = await _p115_client.get_path_id(library.download_path)
    logger.debug(f"[add_task] 获取下载目录 ID: {library.download_path} -> {path_id}")
    if path_id is None:
        logger.error(f"[add_task] 获取下载目录 ID 失败: {library.download_path}")
        raise HTTPException(
            status_code=500, detail=f"获取下载目录 ID 失败: {library.download_path}"
        )

    result = await _p115_client.add_offline_task(request.magnet, path_id)
    if not result.get("state"):
        logger.error(f"[add_task] API 返回失败: {result}")
        raise HTTPException(
            status_code=500,
            detail=f"添加离线任务失败: {result.get('error_msg', '未知错误')}",
        )

    # 添加详细日志以便调试 API 响应
    logger.info(f"API 响应 keys: {list(result.keys())}")
    logger.info(f"API state: {result.get('state')}")

    # 优先级：API 返回的 info_hash > magnet 解析的 > None
    api_info_hash = (
        result.get("info_hash") or result.get("hash") or result.get("task_id")
    )
    final_info_hash = api_info_hash or parsed_info_hash

    logger.info(f"API info_hash: {api_info_hash}")
    logger.info(f"最终 info_hash: {final_info_hash}")

    # 保存到数据库（info_hash 可能为 None）
    try:
        async with get_session() as session:
            # 查询是否存在相同 info_hash 的任务
            result = await session.execute(
                select(OfflineTask).where(OfflineTask.info_hash == final_info_hash)
            )
            existing_task = result.scalar_one_or_none()

            if existing_task:
                # 存在则更新字段
                existing_task.library_name = library.name
                existing_task.name = (
                    request.name if request.name else request.magnet[:50]
                )
                existing_task.status = "added"
                logger.info(f"离线任务已更新: info_hash={final_info_hash}")
            else:
                # 不存在则创建新记录
                offline_task = OfflineTask(
                    info_hash=final_info_hash,
                    name=request.name if request.name else request.magnet[:50],
                    library_name=library.name,
                    status="added",
                )
                session.add(offline_task)
                logger.info(f"离线任务已保存到数据库: info_hash={final_info_hash}")

            await session.commit()
    except Exception as e:
        # 数据库保存失败不影响 API 返回成功
        logger.error(f"保存离线任务失败: {e}")

    # 返回最终的 info_hash（None 时返回空字符串避免 API 响应为 null）
    return success_response(
        data=AddTaskResponse(task_id=final_info_hash or "", message="离线任务添加成功"),
        message="离线任务添加成功",
    )


@router.get("/tasks")
async def get_tasks():
    result = await _p115_client.get_offline_tasks()
    if not result.get("state"):
        raise HTTPException(status_code=500, detail="获取任务列表失败")

    tasks = result.get("tasks") or []
    task_items = [
        TaskItem(
            task_id=task.get("info_hash", ""),
            name=task.get("name", ""),
            status=task.get("status", 0),
            progress=task.get("percent_done", 0),
            add_time=datetime.fromtimestamp(task.get("add_time", 0)),
        )
        for task in tasks
    ]

    return success_response(
        data=TaskListResponse(total=len(task_items), tasks=task_items),
        message="获取任务列表成功",
    )


@router.get("/tasks/{task_id}")
async def get_task_detail(task_id: str):
    task = await _p115_client.get_task_status(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"任务 '{task_id}' 不存在")

    return success_response(
        data=TaskDetailResponse(
            task_id=task.get("info_hash", ""),
            name=task.get("name", ""),
            status=task.get("status", 0),
            progress=task.get("percent_done", 0),
            add_time=datetime.fromtimestamp(task.get("add_time", 0)),
            file_id=str(task.get("file_id")) if task.get("file_id") else None,
            path=task.get("path"),
        ),
        message="获取任务详情成功",
    )


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    result = await _p115_client.delete_offline_task(task_id)
    if not result.get("state"):
        raise HTTPException(status_code=500, detail="删除任务失败")

    return success_response(
        data=DeleteTaskResponse(message="任务删除成功"), message="任务删除成功"
    )
