"""
@description 文件过滤服务核心逻辑
@responsibility 提供视频文件格式判断、大小限制检查及批量文件过滤
"""


def is_video_file(filename: str, formats: list[str]) -> bool:
    """
    判断文件是否为支持的视频格式

    Args:
        filename: 文件名称
        formats: 支持的视频格式列表（不含点号，如 ['mp4', 'mkv']）

    Returns:
        True 表示为支持的视频文件，False 表示不支持或非视频文件
    """
    # 提取文件扩展名（最后一个点之后的部分）
    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[-1].lower()
    return extension in formats


def meets_size_requirement(size_bytes: int, min_size_mb: int) -> bool:
    """
    判断文件大小是否满足最小要求

    Args:
        size_bytes: 文件大小（字节）
        min_size_mb: 最小文件大小（兆字节）

    Returns:
        True 表示满足或超过最小大小，False 表示未达到最小大小
    """
    # 将 MB 转换为字节（1 MB = 1024 * 1024 bytes）
    min_size_bytes = min_size_mb * 1024 * 1024
    return size_bytes >= min_size_bytes


def filter_files(files: list[dict], config: dict) -> list[dict]:
    """
    过滤文件列表，返回符合条件的文件（同时满足格式和大小要求）

    Args:
        files: 文件字典列表，每个字典需要包含 'name' 和 'size' 字段
        config: 配置字典，需要包含以下字段：
            - video_formats: 支持的视频格式列表
            - min_transfer_size: 最小文件大小（MB）

    Returns:
        过滤后的文件列表，保留原始文件字典的所有字段
    """
    video_formats = config.get("video_formats", [])
    min_transfer_size = config.get("min_transfer_size", 0)

    result = []
    for file in files:
        # 115 API fs_files 返回字段: n=文件名, s=文件大小, fid=文件ID(仅文件有), cid=目录ID
        # 通过 fid 是否存在判断：目录没有 fid 字段，文件有 fid 字段
        file_name = file.get("n", "")
        file_size = file.get("s", 0) or file.get("sz", 0) or file.get("size", 0)
        is_directory = "fid" not in file  # 目录没有 fid 字段

        if is_directory:
            # 跳过目录
            continue

        if is_video_file(file_name, video_formats) and meets_size_requirement(
            file_size, min_transfer_size
        ):
            result.append(file)

    return result
