"""
@description 系统状态接口
@responsibility 处理系统状态和监控任务状态的查询
"""

from typing import TYPE_CHECKING, Optional
from datetime import datetime

from fastapi import APIRouter

from app.schemas.api import StatusResponse, success_response, ApiResponse

if TYPE_CHECKING:
    from app.tasks.monitor import TaskMonitor
    from app.services.p115_client import P115Client

router = APIRouter()

_task_monitor: Optional["TaskMonitor"] = None
_p115_client: Optional["P115Client"] = None
_last_check_time: Optional[datetime] = None


def init_system_router(task_monitor: "TaskMonitor", p115_client: "P115Client"):
    global _task_monitor, _p115_client
    _task_monitor = task_monitor
    _p115_client = p115_client


def update_last_check_time():
    global _last_check_time
    _last_check_time = datetime.now()


@router.get("/status", response_model=ApiResponse[StatusResponse])
async def get_status():
    monitor_running = False
    if _task_monitor is not None:
        if hasattr(_task_monitor, "_task") and _task_monitor._task is not None:
            monitor_running = not _task_monitor._task.done()
        elif hasattr(_task_monitor, "_stop_event"):
            monitor_running = not _task_monitor._stop_event.is_set()

    active_tasks = 0
    if _p115_client is not None:
        try:
            result = await _p115_client.get_offline_tasks()
            if result.get("state"):
                tasks = result.get("tasks", [])
                active_tasks = sum(1 for t in tasks if t.get("status") == 0)
        except Exception:
            pass

    return success_response(
        data=StatusResponse(
            monitor_running=monitor_running,
            active_tasks=active_tasks,
            last_check_time=_last_check_time.isoformat() if _last_check_time else None,
        ),
        message="获取系统状态成功",
    )
