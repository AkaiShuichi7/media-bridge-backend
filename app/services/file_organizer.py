"""
@description 文件整理服务核心逻辑
@responsibility 处理文件整理、重命名、移动及清理操作
"""

import asyncio
from typing import Optional

from loguru import logger

from app.core.database import get_session
from app.models.organize_record import OrganizeRecord
from app.services.file_filter import filter_files, is_video_file, meets_size_requirement
from app.services.fanhao_parser import (
    remove_keywords,
    normalize_filename,
    extract_fanhao,
    normalize_cd_suffix,
    generate_target_path,
    extract_producer,
)


class FileOrganizer:
    """文件整理服务"""

    def __init__(self, p115_client):
        self._client = p115_client
        self._lock = asyncio.Lock()

    async def organize_task(
        self,
        task_info: dict,
        library_config: dict,
        media_config: dict,
        xx_config: Optional[dict] = None,
    ) -> dict:
        """
        整理单个任务的文件

        Args:
            task_info: 任务信息，包含 task_id, info_hash, path_id, name
            library_config: 媒体库配置
            media_config: 媒体配置（视频格式、最小大小）
            xx_config: 成人片库配置（可选）

        Returns:
            整理结果统计 {success_count, failed_count, skipped_count, errors}
        """
        # 添加调试日志
        import traceback

        # 初始化结果变量
        result = {
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "errors": [],
        }

        logger.debug(f"[organize_task] task_info keys: {list(task_info.keys())}")
        logger.debug(
            f"[organize_task] library_config keys: {list(library_config.keys())}"
        )

        try:
            async with self._lock:
                logger.debug(f"[organize_task-1] 获取 task_id 和 path_id")
                task_id = task_info["task_id"]
                task_name = task_info.get("name", "")
                download_path_id = task_info.get("download_path_id", "")

                # 获取任务目录的内容
                # 先查询任务目录 ID 对应的内容
                task_path_id = task_info["path_id"]

                logger.debug(f"[organize_task-2] 调用 list_directory (任务目录)")
                # 使用 list_directory 获取文件列表（内部调用 fs_files）
                dir_response = await self._client.list_directory(task_path_id)

                if not dir_response.get("state"):
                    logger.error(f"任务 {task_id} 获取目录列表失败")
                    return result

                # 添加原始响应日志
                logger.debug(
                    f"[organize_task-2c] list_directory 原始响应 keys: {list(dir_response.keys())}"
                )
                raw_files = dir_response.get("data", [])
                logger.debug(
                    f"[organize_task-2d] list_directory 返回的文件数量: {len(raw_files)}"
                )

                # 打印原始文件的 m 字段值分布
                m_values = {}
                for f in raw_files:
                    m = f.get("m", "N/A")
                    m_values[m] = m_values.get(m, 0) + 1
                logger.debug(f"[organize_task-2e] m 字段值分布: {m_values}")

                # 显示每个文件的原始数据
                for i, f in enumerate(raw_files[:3]):
                    file_name = f.get("n", "")
                    file_size = f.get("s", 0)
                    is_dir = "fid" not in f
                    logger.debug(
                        f"[organize_task-2f] list_directory 原始文件{i + 1}: {file_name} (大小: {file_size}, m={f.get('m')})"
                    )

                files = raw_files

                # 如果任务目录里没有文件，尝试在父目录中查找任务名称对应的目录
                if not files and task_name and download_path_id:
                    logger.debug(
                        f"[organize_task-2a] 任务目录为空，尝试在父目录查找: {task_name}"
                    )
                    parent_response = await self._client.list_directory(
                        download_path_id
                    )

                    if parent_response.get("state"):
                        for item in parent_response.get("data", []):
                            # 查找任务名称对应的目录
                            is_dir = "fid" not in item  # 目录没有 fid 字段
                            if item.get("n") == task_name and is_dir:
                                task_path_id = str(item.get("cid"))
                                logger.debug(
                                    f"[organize_task-2b] 找到任务目录 ID: {task_path_id}"
                                )

                                # 重新查询任务目录内容
                                dir_response = await self._client.list_directory(
                                    task_path_id
                                )
                                if dir_response.get("state"):
                                    files = dir_response.get("data", [])
                                break

                if not files:
                    logger.warning(f"任务 {task_id} 无文件可整理")
                    return result

                logger.debug(f"[organize_task-3] 构建 filter_config")
                filter_config = {
                    "video_formats": media_config.get("video_formats", []),
                    "min_transfer_size": library_config.get(
                        "min_transfer_size", media_config.get("min_transfer_size", 0)
                    ),
                }

                # 添加文件列表的详细日志
                logger.debug(f"[organize_task-3a] 查询到的文件数量: {len(files)}")
                for i, file in enumerate(files[:5]):  # 只打印前5个文件
                    file_name = file.get("n", "")
                    file_size = file.get("s", 0)
                    is_dir = "fid" not in file
                    logger.debug(
                        f"[organize_task-3b] 文件{i + 1}: {file_name} (大小: {file_size}, 目录: {is_dir})"
                    )

                # 添加文件过滤详情日志
                logger.debug(f"[organize_task-3c] 开始过滤文件")
                filtered_files = []
                skipped_files = []
                for f in files:
                    file_name = f.get("n", "")
                    file_size = f.get("s", 0)
                    is_directory = "fid" not in f

                    if is_directory:
                        skipped_files.append(f"{file_name} (目录)")
                        continue

                    if is_video_file(
                        file_name, filter_config["video_formats"]
                    ) and meets_size_requirement(
                        file_size, filter_config["min_transfer_size"]
                    ):
                        filtered_files.append(file_name)
                    else:
                        reason = (
                            "格式不匹配"
                            if not is_video_file(
                                file_name, filter_config["video_formats"]
                            )
                            else "大小不满足"
                        )
                        skipped_files.append(f"{file_name} ({reason})")

                logger.debug(f"[organize_task-3c1] 过滤后保留的文件: {filtered_files}")
                logger.debug(f"[organize_task-3c2] 过滤后跳过的文件: {skipped_files}")

                video_files = filter_files(files, filter_config)
                logger.debug(
                    f"[organize_task-3c] 过滤后的视频文件数量: {len(video_files)}"
                )
                for i, vf in enumerate(video_files):
                    logger.debug(
                        f"[organize_task-3c{3 + i}] 视频文件{i + 1}: {vf.get('n', '')} (m={vf.get('m')}, size={vf.get('s', 0)})"
                    )

                if not video_files:
                    logger.warning(
                        f"任务 {task_id} 无符合条件的视频文件 (共查询 {len(files)} 个文件)"
                    )
                    return result

                logger.debug(f"[organize_task-4] 获取 library_type")
                library_type = library_config.get("type", "system")

                if library_type == "system":
                    logger.debug(f"[organize_task-5] 调用 organize_files_system")
                    organize_result = await self.organize_files_system(
                        video_files,
                        library_config["target_path"],
                        task_id,
                        library_config,
                    )
                elif library_type.startswith("xx-"):
                    producer = extract_producer(library_type)
                    logger.debug(f"[organize_task-6] 调用 organize_files_xx")
                    organize_result = await self.organize_files_xx(
                        video_files,
                        library_config["target_path"],
                        producer,
                        xx_config or {},
                        task_id,
                        library_config,
                    )
                else:
                    logger.warning(f"未知的媒体库类型: {library_type}")
                    return result

                logger.debug(f"[organize_task-7] 返回结果")
                result["success_count"] = organize_result["success_count"]
                result["failed_count"] = organize_result["failed_count"]
                result["skipped_count"] = organize_result["skipped_count"]
                result["errors"] = organize_result["errors"]

                return result
        except KeyError as e:
            logger.error(f"[organize_task-KeyError] KeyError: {e}")
            logger.error(f"[organize_task-KeyError] 完整的 task_info: {task_info}")
            logger.error(
                f"[organize_task-KeyError] 完整的 library_config: {library_config}"
            )
            logger.error(
                f"[organize_task-KeyError] 堆栈跟踪:\n{traceback.format_exc()}"
            )
            raise
        except Exception as e:
            logger.error(f"[organize_task-Error] {e}")
            logger.error(f"[organize_task-Error] 堆栈跟踪:\n{traceback.format_exc()}")
            raise

            files = dir_response.get("data", [])
            if not files:
                logger.warning(f"任务 {task_id} 无文件可整理")
                return result

            filter_config = {
                "video_formats": media_config.get("video_formats", []),
                "min_transfer_size": library_config.get(
                    "min_transfer_size", media_config.get("min_transfer_size", 0)
                ),
            }
            video_files = filter_files(files, filter_config)

            if not video_files:
                logger.warning(f"任务 {task_id} 无符合条件的视频文件")
                return result

            library_type = library_config.get("type", "system")

            if library_type == "system":
                organize_result = await self.organize_files_system(
                    video_files, library_config["target_path"], task_id, library_config
                )
            elif library_type.startswith("xx-"):
                producer = extract_producer(library_type)
                organize_result = await self.organize_files_xx(
                    video_files,
                    library_config["target_path"],
                    producer,
                    xx_config or {},
                    task_id,
                    library_config,
                )
            else:
                logger.warning(f"未知的媒体库类型: {library_type}")
                return result

            result["success_count"] = organize_result["success_count"]
            result["failed_count"] = organize_result["failed_count"]
            result["skipped_count"] = organize_result["skipped_count"]
            result["errors"] = organize_result["errors"]

            return result

    async def organize_files_system(
        self,
        files: list[dict],
        target_dir: str,
        task_id: str,
        library_config: dict,
    ) -> dict:
        """
        system 类型整理 - 直接移动文件到目标目录

        Args:
            files: 待整理文件列表
            target_dir: 目标目录路径
            task_id: 任务 ID
            library_config: 媒体库配置

        Returns:
            整理结果统计
        """
        result = {
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "errors": [],
        }

        target_id = await self._client.get_path_id(target_dir)
        if not target_id:
            logger.error(f"无法获取目标目录 ID: {target_dir}")
            result["failed_count"] = len(files)
            return result

        for file in files:
            file_id = file.get("fid", 0)
            file_name = file.get("n", "")
            file_size = file.get("sz", 0) or file.get("s", 0)

            logger.debug(f"准备移动文件: file_id={file_id}, file_name={file_name}")
            try:
                move_response = await self._client.move_file(file_id, target_id)

                if move_response.get("state"):
                    result["success_count"] += 1
                    logger.info(f"文件 {file_name} 移动成功")

                    await self.save_organize_record(
                        {
                            "task_id": task_id,
                            "source_path": f"/{file_id}",
                            "target_path": f"{target_dir}/{file_name}",
                            "file_name": file_name,
                            "file_size": file_size,
                            "library_name": library_config.get("name", ""),
                            "status": "success",
                            "error_message": None,
                        }
                    )
                else:
                    result["skipped_count"] += 1
                    logger.warning(
                        f"文件 {file_name} 跳过: {move_response.get('error', '已存在')}"
                    )

                    await self.save_organize_record(
                        {
                            "task_id": task_id,
                            "source_path": f"/{file_id}",
                            "target_path": f"{target_dir}/{file_name}",
                            "file_name": file_name,
                            "file_size": file_size,
                            "library_name": library_config.get("name", ""),
                            "status": "skipped",
                            "error_message": move_response.get("error", "文件已存在"),
                        }
                    )

            except Exception as e:
                result["failed_count"] += 1
                result["errors"].append(str(e))
                logger.error(f"文件 {file_name} 整理失败: {e}")

                await self.save_organize_record(
                    {
                        "task_id": task_id,
                        "source_path": f"/{file_id}",
                        "target_path": f"{target_dir}/{file_name}",
                        "file_name": file_name,
                        "file_size": file_size,
                        "library_name": library_config.get("name", ""),
                        "status": "failed",
                        "error_message": str(e),
                    }
                )

        return result

    async def organize_files_xx(
        self,
        files: list[dict],
        target_dir: str,
        producer: str,
        xx_config: dict,
        task_id: str,
        library_config: dict,
    ) -> dict:
        """
        xx-片商类型整理 - 处理番号提取、重命名和移动

        Args:
            files: 待整理文件列表
            target_dir: 目标目录路径
            producer: 片商名称
            xx_config: 成人片库配置（包含 remove_keywords）
            task_id: 任务 ID
            library_config: 媒体库配置

        Returns:
            整理结果统计
        """
        result = {
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "errors": [],
        }

        file_count = len(files)
        keywords = xx_config.get("remove_keywords", [])

        for file in files:
            file_id = file.get("fid", 0)
            original_name = file.get("n", "")
            file_size = file.get("sz", 0) or file.get("s", 0)

            logger.debug(f"准备移动文件: file_id={file_id}, file_name={original_name}")
            try:
                processed_name = remove_keywords(original_name, keywords)
                processed_name = normalize_filename(processed_name)

                fanhao = extract_fanhao(processed_name)
                if not fanhao:
                    result["skipped_count"] += 1
                    logger.warning(f"无法从 {original_name} 提取番号，跳过")
                    continue

                processed_name = normalize_cd_suffix(processed_name, file_count)
                final_target_path = generate_target_path(
                    processed_name, target_dir, producer
                )
                target_dir_path = "/".join(final_target_path.rsplit("/", 1)[:-1])
                target_id = await self._client.get_path_id(target_dir_path)

                if not target_id:
                    result["failed_count"] += 1
                    result["errors"].append(f"无法创建目标目录: {target_dir_path}")
                    continue

                rename_response = await self._client.rename_file(
                    file_id, processed_name
                )
                if not rename_response.get("state"):
                    error_msg = rename_response.get("error", "未知错误")
                    errno = rename_response.get("errno", "N/A")
                    logger.warning(
                        f"重命名失败 (errno={errno}): {error_msg}，使用原文件名: {original_name}"
                    )

                move_response = await self._client.move_file(file_id, target_id)

                if move_response.get("state"):
                    result["success_count"] += 1
                    logger.info(f"文件 {original_name} -> {processed_name} 整理成功")

                    await self.save_organize_record(
                        {
                            "task_id": task_id,
                            "source_path": f"/{file_id}/{original_name}",
                            "target_path": final_target_path,
                            "file_name": processed_name,
                            "file_size": file_size,
                            "library_name": library_config.get("name", ""),
                            "status": "success",
                            "error_message": None,
                        }
                    )
                else:
                    result["skipped_count"] += 1
                    logger.warning(
                        f"文件 {processed_name} 跳过: {move_response.get('error', '已存在')}"
                    )

            except Exception as e:
                result["failed_count"] += 1
                result["errors"].append(str(e))
                logger.error(f"文件 {original_name} 整理失败: {e}")

        return result

    async def save_organize_record(self, record: dict) -> None:
        """
        保存整理记录到数据库

        Args:
            record: 整理记录字典
        """
        try:
            async with get_session() as session:
                organize_record = OrganizeRecord(
                    task_id=record["task_id"],
                    source_path=record["source_path"],
                    target_path=record["target_path"],
                    file_name=record["file_name"],
                    file_size=record["file_size"],
                    library_name=record["library_name"],
                    status=record["status"],
                    error_message=record.get("error_message"),
                )
                session.add(organize_record)
                await session.commit()
                logger.debug(f"整理记录已保存: {record['file_name']}")
        except Exception as e:
            logger.error(f"保存整理记录失败: {e}")

    async def cleanup_source(
        self, task_id: str, info_hash: str, source_files: list[dict]
    ) -> None:
        """
        清理源文件和离线任务

        Args:
            task_id: 任务 ID
            info_hash: 离线任务 hash
            source_files: 源文件列表
        """
        for file in source_files:
            file_id = file.get("fid", 0)
            file_name = file.get("n", "")
            logger.debug(f"准备删除源文件: file_id={file_id}, file_name={file_name}")
            try:
                await self._client.delete_file(file_id)
                logger.info(f"源文件 {file_name} 已删除")
            except Exception as e:
                logger.error(f"删除源文件 {file_name} 失败: {e}")

        try:
            await self._client.delete_offline_task(info_hash)
            logger.info(f"离线任务 {task_id} 已删除")
        except Exception as e:
            logger.error(f"删除离线任务 {task_id} 失败: {e}")
