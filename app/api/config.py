"""
@description 配置管理接口
@responsibility 处理配置的查询和修改操作
"""

from typing import TYPE_CHECKING

from fastapi import APIRouter

from app.schemas.api import (
    ConfigResponse,
    P115ConfigResponse,
    MediaConfigResponse,
    LibraryItem,
    XXConfigResponse,
    UpdateConfigRequest,
    UpdateConfigResponse,
    LibrariesResponse,
)

if TYPE_CHECKING:
    from app.core.config import Config

router = APIRouter()

_config: "Config" = None


def init_config_router(config: "Config"):
    global _config
    _config = config


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    libraries = [
        LibraryItem(
            name=lib.name,
            download_path=lib.download_path,
            target_path=lib.target_path,
            type=lib.type,
            min_transfer_size=lib.min_transfer_size,
        )
        for lib in _config.media.libraries
    ]

    xx_config = XXConfigResponse(
        remove_keywords=_config.media.xx.remove_keywords if _config.media.xx else []
    )

    return ConfigResponse(
        p115=P115ConfigResponse(
            rotation_training_interval_min=_config.p115.rotation_training_interval_min,
            rotation_training_interval_max=_config.p115.rotation_training_interval_max,
        ),
        media=MediaConfigResponse(
            min_transfer_size=_config.media.min_transfer_size,
            video_formats=_config.media.video_formats,
            libraries=libraries,
            xx=xx_config,
        ),
    )


@router.put("/config", response_model=UpdateConfigResponse)
async def update_config(request: UpdateConfigRequest):
    if request.p115:
        if request.p115.rotation_training_interval_min is not None:
            _config.p115.rotation_training_interval_min = (
                request.p115.rotation_training_interval_min
            )
        if request.p115.rotation_training_interval_max is not None:
            _config.p115.rotation_training_interval_max = (
                request.p115.rotation_training_interval_max
            )

    if request.media:
        if request.media.min_transfer_size is not None:
            _config.media.min_transfer_size = request.media.min_transfer_size

    return UpdateConfigResponse(message="配置更新成功")


@router.get("/libraries", response_model=LibrariesResponse)
async def get_libraries():
    libraries = [
        LibraryItem(
            name=lib.name,
            download_path=lib.download_path,
            target_path=lib.target_path,
            type=lib.type,
            min_transfer_size=lib.min_transfer_size,
        )
        for lib in _config.media.libraries
    ]

    return LibrariesResponse(libraries=libraries)
