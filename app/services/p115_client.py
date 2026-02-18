"""
@description p115client 异步封装
@responsibility 提供 115 网盘离线下载和文件操作的统一接口
"""

import asyncio
import random
import re
import time
from typing import Any, Optional

from loguru import logger
from p115client import P115Client as P115SyncClient


class P115Client:
    """p115 客户端单例封装"""

    _instance: Optional["P115Client"] = None
    _lock: asyncio.Lock = asyncio.Lock()
    _client: Optional[P115SyncClient] = None
    _cookies: Optional[str] = None

    def __init__(self, cookies: str):
        self._cookies = cookies
        self._client = P115SyncClient(cookies, check_for_relogin=False)

    @classmethod
    async def get_client(cls, cookies: str) -> "P115Client":
        """获取客户端实例（单例模式）"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(cookies)
                    logger.info("p115 客户端实例已创建")
        return cls._instance

    async def _retry_with_backoff(
        self, func, *args, max_retries: int = 3, **kwargs
    ) -> Any:
        """执行 API 调用并在失败时自动重试（指数退避）"""
        for attempt in range(max_retries):
            try:
                await self._rate_limit()
                result = await asyncio.to_thread(func, *args, **kwargs)
                return result
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"API 调用失败，已达到最大重试次数: {e}")
                    raise

                backoff_time = 2**attempt
                logger.warning(
                    f"API 调用失败（第 {attempt + 1} 次），{backoff_time}秒后重试: {e}"
                )
                await asyncio.sleep(backoff_time)

    async def _rate_limit(self) -> None:
        """API 调用速率限制（随机延迟 0.5-1 秒）"""
        delay = random.uniform(0.5, 1.0)
        await asyncio.sleep(delay)

    async def add_offline_task(self, magnet: str, path_id: str) -> dict:
        """添加离线下载任务"""
        return await self._retry_with_backoff(
            self._client.offline_add_url, {"url": magnet, "wp_path_id": path_id}
        )

    async def get_offline_tasks(self) -> dict:
        """获取离线任务列表"""
        return await self._retry_with_backoff(self._client.offline_list)

    async def get_task_status(self, info_hash: str) -> Optional[dict]:
        """获取单个任务状态"""
        tasks_response = await self.get_offline_tasks()

        if not tasks_response.get("state"):
            return None

        tasks = tasks_response.get("tasks") or []
        for task in tasks:
            if task.get("info_hash") == info_hash:
                return task

        return None

    async def delete_offline_task(self, info_hash: str) -> dict:
        """删除离线任务"""
        return await self._retry_with_backoff(
            self._client.offline_remove, {"hash": info_hash, "flag": 1}
        )

    async def clear_completed_tasks(self) -> dict:
        """清理已完成的离线任务"""
        return await self._retry_with_backoff(self._client.offline_clear)

    async def get_path_id(
        self, path: str, mkdir: bool = True, library_name: str = "default"
    ) -> Optional[str]:
        """
        获取目录 ID（带数据库缓存）
        - 缓存命中：直接返回
        - 缓存未命中：遍历 fs_files，成功后写入缓存
        """
        try:
            # 根目录特殊处理
            if not path or path == "/":
                return "0"

            # 1. 规范化路径
            normalized_path = self._normalize_path(path)

            # 2. 使用分层缓存查询
            start_id, remaining_path = await self._find_nearest_cached_ancestor(
                library_name, normalized_path
            )

            if not remaining_path:
                # 完全命中缓存
                logger.debug(f"缓存完全命中: {normalized_path} -> {start_id}")
                return start_id

            logger.debug(
                f"缓存部分命中，从 cid={start_id} 开始遍历剩余路径: {remaining_path}"
            )

            # 3. 从缓存位置开始遍历剩余路径
            parts = remaining_path.split("/")
            current_id = start_id

            # 计算已遍历的路径前缀（用于目录创建）
            normalized_parts = normalized_path.strip("/").split("/")
            traversed_count = len(normalized_parts) - len(parts)

            for idx, part in enumerate(parts):
                if not part:
                    continue

                # 使用 fs_files 列出当前目录内容
                result = await self._retry_with_backoff(
                    self._client.fs_files, {"cid": current_id, "limit": 1000}
                )

                # 查找匹配的子目录 (目录没有 fid 字段, n 是名称)
                found = False
                for item in result.get("data", []):
                    is_dir = "fid" not in item  # 目录没有 fid 字段
                    if item.get("n") == part and is_dir:
                        current_id = str(item.get("cid"))  # 目录使用 cid
                        logger.debug(f"找到目录: {part}, cid={current_id}")
                        found = True
                        break

                if not found:
                    if mkdir:
                        # 创建目录（使用完整路径）
                        full_path_to_create = "/" + "/".join(
                            normalized_parts[: traversed_count + idx + 1]
                        )
                        create_result = await self._retry_with_backoff(
                            self._client.fs_makedirs_app, full_path_to_create
                        )
                        if create_result.get("state"):
                            # 创建后重新获取 ID
                            result = await self._retry_with_backoff(
                                self._client.fs_files,
                                {"cid": current_id, "limit": 1000},
                            )
                            for item in result.get("data", []):
                                is_dir = "fid" not in item
                                if item.get("n") == part and is_dir:
                                    current_id = str(item.get("cid"))
                                    logger.debug(
                                        f"创建后找到目录: {part}, cid={current_id}"
                                    )
                                    found = True
                                    break

                    if not found:
                        logger.error(f"目录不存在且创建失败: {normalized_path}")
                        return None

            # 4. 成功获取 path_id，写入完整路径缓存
            if current_id != "0":
                if self._is_temp_directory(normalized_path):
                    # 临时目录不缓存
                    logger.debug(f"临时目录跳过缓存: {normalized_path}")
                else:
                    # 稳定目录正常缓存
                    await self._set_cached_path_id(
                        library_name, normalized_path, int(current_id)
                    )
                    logger.debug(f"缓存写入: {normalized_path} -> {current_id}")

            return current_id
        except Exception as e:
            logger.error(f"获取目录 ID 失败: {path}, 错误: {e}")
            return None

    async def move_file(self, file_id: str, target_id: str) -> dict:
        """移动文件到目标目录"""
        return await self._retry_with_backoff(
            self._client.fs_move, {"fid": file_id, "pid": target_id}
        )

    async def rename_file(self, file_id: str, new_name: str) -> dict:
        """重命名文件"""
        return await self._retry_with_backoff(
            self._client.fs_rename, (int(file_id), new_name)
        )

    async def delete_file(self, file_id: str) -> dict:
        """删除文件"""
        return await self._retry_with_backoff(self._client.fs_delete, file_id)

    async def list_directory(self, path_id: str) -> dict:
        """列出目录内容"""
        return await self._retry_with_backoff(
            self._client.fs_files, {"cid": path_id, "limit": 1000}
        )

    async def verify_cookies(self) -> bool:
        """验证 cookies 有效性"""
        try:
            result = await self._retry_with_backoff(self._client.user_info)
            return result.get("state", False)
        except Exception as e:
            logger.error(f"验证 cookies 失败: {e}")
            return False

    async def _find_nearest_cached_ancestor(
        self, library_name: str, path: str
    ) -> tuple[str | None, str]:
        """
        查找最近的已缓存祖先目录

        Args:
            library_name: 库名称
            path: 目标路径，如 /云下载/测试/目标/其他/MUDR-359

        Returns:
            tuple: (缓存的路径ID, 需要继续遍历的相对路径)
            例如: 如果 /云下载/测试/目标 被缓存，返回 (cid, "其他/MUDR-359")
        """
        parts = path.strip("/").split("/")

        # 从完整路径开始，逐级向上查找缓存
        for i in range(len(parts), 0, -1):
            ancestor_path = "/" + "/".join(parts[:i])
            cached_id = await self._get_cached_path_id(library_name, ancestor_path)
            if cached_id is not None:
                remaining_path = "/".join(parts[i:]) if i < len(parts) else ""
                logger.debug(
                    f"找到缓存祖先: {ancestor_path} -> {cached_id}, 剩余路径: {remaining_path or '(空)'}"
                )
                return str(cached_id), remaining_path

        # 没有找到任何缓存，从根目录开始
        logger.debug(f"未找到任何缓存祖先，从根目录开始遍历")
        return "0", path.strip("/")

    def _is_temp_directory(self, path: str) -> bool:
        """
        判断路径是否是临时目录（如番号目录）

        临时目录特征:
        - 路径最后一级
        - 匹配番号模式: 大写字母 + 横杠 + 数字，如 MUDR-359, ABP-123, SSIS-001

        Args:
            path: 完整路径，如 /云下载/测试/目标/其他/MUDR-359

        Returns:
            bool: True 表示是临时目录，False 表示是稳定目录
        """
        last_part = path.rsplit("/", 1)[-1]
        # 番号模式：大写字母 + 横杠 + 数字
        # 例如: MUDR-359, ABP-123, SSIS-001, IPX-12345
        is_temp = bool(re.match(r"^[A-Z]+-\d+$", last_part))

        if is_temp:
            logger.debug(f"检测到临时目录: {last_part}")

        return is_temp

    def _normalize_path(self, path: str) -> str:
        """规范化路径为缓存 key"""
        if not path or path == "/":
            return "/"
        # 去除首尾斜杠，分割后过滤空字符串，重新拼接
        parts = [p for p in path.strip("/").split("/") if p]
        return "/" + "/".join(parts)

    async def _get_cached_path_id(self, library_name: str, path: str) -> Optional[int]:
        """从缓存读取 path_id（读时过滤过期）"""
        from app.core.database import get_session
        from app.models.path_id_cache import PathIdCache
        from sqlalchemy import select

        normalized_path = self._normalize_path(path)
        now = int(time.time())

        async with get_session() as session:
            result = await session.execute(
                select(PathIdCache.path_id).where(
                    PathIdCache.library_name == library_name,
                    PathIdCache.path == normalized_path,
                    PathIdCache.expires_at > now,  # 读时过滤过期
                )
            )
            row = result.scalar_one_or_none()
            return row if row is not None else None

    async def _set_cached_path_id(
        self,
        library_name: str,
        path: str,
        path_id: int,
        ttl_seconds: int = 600,
    ) -> None:
        """写入缓存（UPSERT，并发安全）"""
        from app.core.database import get_session
        from sqlalchemy import text

        normalized_path = self._normalize_path(path)
        now = int(time.time())
        expires_at = now + ttl_seconds

        async with get_session() as session:
            # 使用原生 SQL 实现 UPSERT（性能更好）
            await session.execute(
                text("""
                INSERT INTO path_id_cache 
                (library_name, path, path_id, expires_at, hit_count, created_at, updated_at)
                VALUES (:library_name, :path, :path_id, :expires_at, 0, :now, :now)
                ON CONFLICT(library_name, path) DO UPDATE SET
                    path_id = excluded.path_id,
                    expires_at = excluded.expires_at,
                    updated_at = excluded.updated_at
            """),
                {
                    "library_name": library_name,
                    "path": normalized_path,
                    "path_id": path_id,
                    "expires_at": expires_at,
                    "now": now,
                },
            )
            await session.commit()

    async def _cleanup_expired_cache(self, batch_size: int = 1000) -> int:
        """清理过期缓存（批量删除，返回删除数量）"""
        from app.core.database import get_session
        from sqlalchemy import text

        now = int(time.time())
        total_deleted = 0

        async with get_session() as session:
            # 批量删除过期记录
            result = await session.execute(
                text("""
                DELETE FROM path_id_cache 
                WHERE id IN (
                    SELECT id FROM path_id_cache 
                    WHERE expires_at <= :now 
                    LIMIT :limit
                )
            """),
                {"now": now, "limit": batch_size},
            )
            await session.commit()
            total_deleted = result.rowcount or 0

        return total_deleted
