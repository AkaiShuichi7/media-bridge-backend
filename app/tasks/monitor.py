"""
@description 后台监控任务核心逻辑
@responsibility 监控115离线任务状态，任务完成时触发文件整理，失败时记录到数据库
"""

import asyncio
import random
import signal
from datetime import datetime
from typing import Optional

from loguru import logger
from sqlalchemy import select

from app.core.database import get_session
from app.models.offline_task import OfflineTask


class TaskMonitor:
    """后台监控任务管理器"""

    def __init__(self, p115_client, file_organizer, config):
        self._client = p115_client
        self._organizer = file_organizer
        self._config = config
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._processed_hashes: set[str] = set()

    async def start_monitor(self) -> None:
        """启动监控任务"""
        if self._task is not None and not self._task.done():
            logger.warning("监控任务已在运行中")
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self._monitor_loop())
        self._setup_signal_handlers()
        logger.info("后台监控任务已启动")

    async def stop_monitor(self) -> None:
        """停止监控任务"""
        if self._task is None:
            return

        self._stop_event.set()
        try:
            await asyncio.wait_for(self._task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("等待监控任务停止超时，强制取消")
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("后台监控任务已停止")

    async def check_tasks(self) -> None:
        """检查所有离线任务状态 - 只处理系统添加的任务"""
        try:
            # 1. 查询数据库获取系统任务的 info_hash 列表
            async with get_session() as session:
                result = await session.execute(
                    select(OfflineTask.info_hash).where(
                        OfflineTask.status.in_(["added", "downloading"])
                    )
                )
                system_hashes = set(row[0] for row in result.fetchall())

            if not system_hashes:
                logger.debug("没有需要监控的系统任务")
                return

            # 2. 获取 115 离线任务列表
            response = await self._client.get_offline_tasks()
            if not response.get("state"):
                logger.error("获取离线任务列表失败")
                return

            # 3. 只处理系统添加的任务
            tasks = response.get("tasks") or []
            for task in tasks:
                info_hash = task.get("info_hash")
                if info_hash and info_hash in system_hashes:
                    await self._process_task(task)

        except Exception as e:
            logger.error(f"检查任务时发生错误: {e}")

    async def _process_task(self, task: dict) -> None:
        """处理单个离线任务"""
        info_hash = task.get("info_hash")
        status = task.get("status")
        name = task.get("name", "未知任务")

        if info_hash in self._processed_hashes:
            return

        if status == 2:
            logger.info(f"任务 [{name}] 已完成，开始整理文件")
            await self._handle_completed_task(task)
            self._processed_hashes.add(info_hash)

        elif status < 0:  # 负数表示失败（如 -1）
            logger.warning(f"任务 [{name}] 下载失败 (status={status})")
            await self._handle_failed_task(task)
            self._processed_hashes.add(info_hash)

    async def _handle_completed_task(self, task: dict) -> None:
        """处理已完成的任务 - 触发文件整理"""
        info_hash = task.get("info_hash")

        # 通过数据库查询 library_name
        library_config = None
        if info_hash:
            try:
                async with get_session() as session:
                    result = await session.execute(
                        select(OfflineTask.library_name).where(
                            OfflineTask.info_hash == info_hash
                        )
                    )
                    library_name = result.scalar_one_or_none()
                    if library_name:
                        library_config = self._find_library_by_name(library_name)
                        logger.debug(f"通过数据库找到 library: {library_name}")
            except Exception as e:
                logger.error(f"查询 library_name 失败: {e}")

        if library_config is None:
            logger.error(
                f"无法确定任务 [{task.get('name', 'unknown')}] 的 library 配置，跳过整理"
            )
            return

        task_path = task.get("path", "")
        download_path_id = ""
        logger.debug(f"[handle_completed] 完整任务数据: {task}")
        logger.debug(f"[handle_completed] 任务路径: {task_path}")
        if task_path:
            parent_path = "/".join(task_path.rstrip("/").split("/")[:-1])
            logger.debug(f"[handle_completed] 父目录路径: {parent_path}")
            if parent_path:
                download_path_id = await self._client.get_path_id(parent_path)
                logger.debug(
                    f"[handle_completed] 下载路径 ID: {parent_path} -> {download_path_id}"
                )

        task_info = {
            "task_id": task.get("info_hash"),
            "info_hash": task.get("info_hash"),
            "name": task.get("name", "未知任务"),
            "path_id": str(task.get("file_id", "")),
            "download_path_id": download_path_id or "",
        }

        logger.debug(f"任务信息: task_info keys = {list(task_info.keys())}")
        logger.debug(f"完整 task_info: {task_info}")

        media_config = {
            "video_formats": self._config.media.video_formats,
            "min_transfer_size": self._config.media.min_transfer_size,
        }

        xx_config = None
        if hasattr(self._config.media, "xx") and self._config.media.xx:
            xx_config = {"remove_keywords": self._config.media.xx.remove_keywords}

        lib_dict = {
            "name": library_config.name,
            "download_path": library_config.download_path,
            "target_path": library_config.target_path,
            "type": library_config.type,
            "min_transfer_size": library_config.min_transfer_size,
        }

        try:
            result = await self._organizer.organize_task(
                task_info, lib_dict, media_config, xx_config
            )
            logger.info(
                f"任务整理完成: 成功 {result['success_count']}, "
                f"失败 {result['failed_count']}, 跳过 {result['skipped_count']}"
            )

            try:
                await self._client.delete_offline_task(task.get("info_hash"))
                logger.info(f"任务 [{task_info['name']}] 已自动清理原始文件")
            except Exception as e:
                logger.warning(f"任务 [{task_info['name']}] 清理失败: {e}")

        except Exception as e:
            logger.error(f"整理任务时发生错误: {e}")

    async def _handle_failed_task(self, task: dict) -> None:
        """处理失败的任务 - 保存记录到数据库"""
        try:
            async with get_session() as session:
                offline_task = OfflineTask(
                    info_hash=task.get("info_hash"),
                    name=task.get("name"),
                    library_name=None,
                    status="failed",
                    add_time=datetime.fromtimestamp(task.get("add_time", 0)),
                    error_message=task.get("error_msg", "下载失败"),
                )
                session.add(offline_task)
                await session.commit()
                logger.info(f"失败任务已记录到数据库: {task.get('name')}")
        except Exception as e:
            logger.error(f"保存失败任务记录时出错: {e}")

    def _find_library_by_name(self, name: str):
        """根据名称查找媒体库配置"""
        for library in self._config.media.libraries:
            if library.name == name:
                return library
        return None

    def _get_random_interval(self) -> float:
        """获取随机轮询间隔（秒）"""
        min_interval = self._config.p115.rotation_training_interval_min
        max_interval = self._config.p115.rotation_training_interval_max
        return random.uniform(min_interval, max_interval)

    async def _monitor_loop(self) -> None:
        """监控主循环"""
        while not self._stop_event.is_set():
            try:
                await self.check_tasks()
            except Exception as e:
                logger.error(f"监控循环出错: {e}")

            interval = self._get_random_interval()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    def _setup_signal_handlers(self) -> None:
        """设置信号处理器"""
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, self._handle_shutdown, sig, None)
        except (NotImplementedError, RuntimeError):
            for sig in (signal.SIGTERM, signal.SIGINT):
                signal.signal(sig, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame) -> None:
        """信号处理：优雅关闭"""
        sig_name = signal.Signals(signum).name if signum else "UNKNOWN"
        logger.info(f"收到 {sig_name} 信号，正在优雅关闭...")
        self._stop_event.set()


async def start_monitor(p115_client, file_organizer, config) -> TaskMonitor:
    """创建并启动监控实例的便捷函数"""
    monitor = TaskMonitor(p115_client, file_organizer, config)
    await monitor.start_monitor()
    return monitor


async def stop_monitor(monitor: TaskMonitor) -> None:
    """停止监控实例的便捷函数"""
    await monitor.stop_monitor()
