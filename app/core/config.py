"""
@description 配置管理模块
@responsibility 加载和验证 config.yaml，支持环境变量覆盖
"""

import os
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class P115Config(BaseModel):
    """115 账户配置"""

    cookies: str = Field(..., description="115 Cookies 字符串")
    rotation_training_interval_min: int = Field(..., description="轮询间隔最小值（秒）")
    rotation_training_interval_max: int = Field(..., description="轮询间隔最大值（秒）")


class LibraryConfig(BaseModel):
    """媒体库配置"""

    name: str = Field(..., description="媒体库名称")
    download_path: str = Field(..., description="下载目录路径")
    target_path: str = Field(..., description="目标目录路径")
    type: str = Field(..., description="媒体库类型（system/xx-{studio}）")
    min_transfer_size: int = Field(
        default=0, description="最小传输大小（MB），<=0 使用默认值"
    )


class XXConfig(BaseModel):
    """成人片库（xx）配置"""

    remove_keywords: list[str] = Field(
        default_factory=list, description="需要移除的关键词列表"
    )


class MediaConfig(BaseModel):
    """媒体相关配置"""

    min_transfer_size: int = Field(..., description="默认最小传输大小（MB）")
    libraries: list[LibraryConfig] = Field(..., description="媒体库列表")
    video_formats: list[str] = Field(..., description="支持的视频格式列表")
    xx: XXConfig = Field(default_factory=XXConfig, description="成人片库配置")


class Config(BaseModel):
    """全局配置"""

    p115: P115Config = Field(..., description="115 账户配置")
    media: MediaConfig = Field(..., description="媒体配置")


def get_config_path() -> Path:
    """获取配置文件路径"""
    # 优先使用 CONFIG_PATH 环境变量，否则使用项目根目录的 config.yaml
    if config_path_str := os.environ.get("CONFIG_PATH"):
        return Path(config_path_str)
    return Path(__file__).parent.parent.parent / "config.yaml"


def load_config() -> Config:
    """加载配置文件并应用环境变量覆盖"""
    config_path = get_config_path()

    # 配置文件不存在时生成模板并退出
    if not config_path.exists():
        _generate_config_template(config_path)
        print(f"错误: 配置文件不存在: {config_path}")
        print(f"已生成配置模板: {config_path.parent / 'config.example.yaml'}")
        sys.exit(1)

    # 加载 YAML 配置
    with open(config_path) as f:
        config_data = yaml.safe_load(f)

    # 解析为 Pydantic 模型（验证数据结构）
    config = Config(**config_data)

    # 应用环境变量覆盖
    if cookies := os.environ.get("P115_COOKIES"):
        config.p115.cookies = cookies

    return config


def _generate_config_template(config_path: Path) -> None:
    """生成配置模板文件"""
    template_path = config_path.parent / "config.example.yaml"

    if template_path.exists():
        return

    template_content = """# 115网盘相关配置
p115:
  # 账号信息（Cookies）
  cookies: "UID=your_uid; CID=your_cid; SEID=your_seid; KID=your_kid"
  # 115任务监控的轮训间隔最小值（秒）
  rotation_training_interval_min: 60
  # 115任务监控的轮训间隔最大值（秒）
  rotation_training_interval_max: 80

# 媒体相关配置
media:
  # 默认文件大小阈值（MB），大于此大小的视频文件才会被移动
  min_transfer_size: 200
  # 媒体库列表配置
  libraries:
    # 下载地址和下载完成后移动文件的目标目录映射
    - name: "测试"
      download_path: "/云下载/测试/下载" # 离线下载文件的存放目录
      target_path: "/云下载/测试/目标" # 下载完成后移动文件的目标目录
      min_transfer_size: 100 # 覆盖默认的最小传输大小（MB），小于等于0表示使用默认值
      # 媒体库类型，决定了如何处理下载完成的视频文件，目前支持以下类型：
      # system：表示媒体服务器创建的可搜刮媒体库，不需要对其进行特殊处理，直接将视频文件移动到目标目录即可
      # xx-片商：标识成人片库，xx表示为成人片库，我们要对其进行特殊处理（重命名等操作），片商表示成人片库的片商名称
      type: "system"
  # xx库配置，xx表示成人片库，我们需要对其进行特殊处理（重命名等操作）
  xx:
    # 需要移除视频文件名中的哪些关键词
    remove_keywords: ["hhd800.com@", "_X1080X", "[98t.tv]", "_60FPS", "-4k"]

  # 视频文件格式列表，只有这些格式的视频文件才会被移动
  video_formats:
    [
      "mp4",
      "mkv",
      "ts",
      "iso",
      "rmvb",
      "avi",
      "mov",
      "mpeg",
      "mpg",
      "wmv",
      "3gp",
      "asf",
      "m4v",
      "flv",
      "m2ts",
      "tp",
      "f4v",
    ]
"""

    with open(template_path, "w") as f:
        f.write(template_content)
