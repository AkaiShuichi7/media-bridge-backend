"""
@description 番号解析服务核心逻辑
@responsibility 番号提取、文件名标准化、目标路径生成
"""

import re
from pathlib import Path


FANHAO_PATTERN = re.compile(r"(?<![A-Z0-9])[A-Z]{2,10}-\d{3,5}(?!\d)")


def remove_keywords(filename: str, keywords: list[str]) -> str:
    result = filename
    for keyword in keywords:
        result = result.replace(keyword, "")
    return result


def normalize_filename(filename: str) -> str:
    parts = filename.rsplit(".", 1)
    if len(parts) == 2:
        name, ext = parts
        normalized_name = name.replace(".", "-").upper()
        return f"{normalized_name}.{ext}"
    else:
        return filename.upper()


def extract_fanhao(filename: str) -> str | None:
    match = FANHAO_PATTERN.search(filename)
    if match:
        return match.group()
    return None


def normalize_cd_suffix(filename: str, file_count: int) -> str:
    parts = filename.rsplit(".", 1)
    if len(parts) != 2:
        return filename

    name, ext = parts

    if file_count == 1:
        return filename

    if "-" not in name:
        return filename

    suffix = name.split("-")[-1]

    letter_order = {"A": 1, "B": 2, "C": 3, "D": 4, "U": 1}
    numeric_mapping = {"1": "CD1", "2": "CD2", "3": "CD3", "4": "CD4"}
    part_mapping = {"PART1": "CD1", "PART2": "CD2", "PART3": "CD3", "PART4": "CD4"}

    base_name = "-".join(name.split("-")[:-1])

    if suffix in letter_order:
        order_num = letter_order[suffix]
        if order_num <= file_count:
            return f"{base_name}-CD{order_num}.{ext}"
        else:
            return f"{base_name}-CD1.{ext}"
    elif suffix in numeric_mapping:
        return f"{base_name}-{numeric_mapping[suffix]}.{ext}"
    elif suffix in part_mapping:
        return f"{base_name}-{part_mapping[suffix]}.{ext}"

    return filename


def generate_target_path(filename: str, target_dir: str, producer: str) -> str:
    target_dir = target_dir.rstrip("/")

    fanhao = extract_fanhao(filename)
    if not fanhao:
        raise ValueError(f"无法从文件名中提取番号: {filename}")

    return f"{target_dir}/{producer}/{fanhao}/{filename}"


def extract_producer(library_type: str) -> str | None:
    if not library_type or not library_type.startswith("xx-"):
        return None

    parts = library_type.split("-", 1)
    if len(parts) != 2 or not parts[1]:
        return None

    return parts[1]
