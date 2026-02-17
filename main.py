"""
@description FastAPI 应用入口
@responsibility 初始化应用、集成路由、启动监控任务、验证 cookies
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from loguru import logger

from app.api import tasks, organize, config, system
from app.api.tasks import init_tasks_router
from app.api.config import init_config_router
from app.api.system import init_system_router
from app.core.config import load_config
from app.core.database import init_db, get_session
from app.services.p115_client import P115Client
from app.services.file_organizer import FileOrganizer
from app.tasks.monitor import TaskMonitor


config_obj = None
p115_client: Optional[P115Client] = None
task_monitor: Optional[TaskMonitor] = None
file_organizer: Optional[FileOrganizer] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global config_obj, p115_client, task_monitor, file_organizer

    logger.info("应用启动中...")

    config_obj = load_config()
    logger.info("配置加载完成")

    await init_db()
    logger.info("数据库初始化完成")

    p115_client = await P115Client.get_client(config_obj.p115.cookies)

    cookies_valid = await p115_client.verify_cookies()
    if not cookies_valid:
        logger.error("115 Cookies 验证失败，请检查配置")
    else:
        logger.info("115 Cookies 验证成功")

    init_tasks_router(p115_client, config_obj)
    init_config_router(config_obj)

    file_organizer = FileOrganizer(p115_client)
    task_monitor = TaskMonitor(p115_client, file_organizer, config_obj)

    init_system_router(task_monitor, p115_client)

    await task_monitor.start_monitor()
    logger.info("后台监控任务已启动")

    yield

    if task_monitor:
        await task_monitor.stop_monitor()
        logger.info("后台监控任务已停止")

    logger.info("应用已关闭")


app = FastAPI(
    title="115 离线任务管理器",
    description="管理 115 网盘离线下载任务并自动整理文件",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(tasks.router, prefix="/api", tags=["tasks"])
app.include_router(organize.router, prefix="/api", tags=["organize"])
app.include_router(config.router, prefix="/api", tags=["config"])
app.include_router(system.router, prefix="/api", tags=["system"])


@app.get("/")
async def root():
    return {"message": "115 离线任务管理器 API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
