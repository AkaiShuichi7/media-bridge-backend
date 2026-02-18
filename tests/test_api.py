"""
@description API 接口测试
@responsibility 测试所有 FastAPI 接口的正确性
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from app.api import tasks, organize, config, system
from app.api.tasks import init_tasks_router
from app.api.config import init_config_router
from app.api.system import init_system_router


@pytest.fixture
def mock_config():
    cfg = MagicMock()
    cfg.p115.cookies = "test_cookies"
    cfg.p115.rotation_training_interval_min = 60
    cfg.p115.rotation_training_interval_max = 80

    library1 = MagicMock()
    library1.name = "电影库"
    library1.download_path = "/云下载/电影"
    library1.target_path = "/媒体库/电影"
    library1.type = "system"
    library1.min_transfer_size = 100

    library2 = MagicMock()
    library2.name = "成人库"
    library2.download_path = "/云下载/成人"
    library2.target_path = "/媒体库/成人"
    library2.type = "xx-SSNI"
    library2.min_transfer_size = 200

    cfg.media.libraries = [library1, library2]
    cfg.media.video_formats = ["mp4", "mkv"]
    cfg.media.min_transfer_size = 150
    cfg.media.xx.remove_keywords = ["hhd800.com@"]

    return cfg


@pytest.fixture
def mock_p115_client():
    client = AsyncMock()
    client.verify_cookies = AsyncMock(return_value=True)
    client.add_offline_task = AsyncMock(
        return_value={"state": True, "info_hash": "abc123hash"}
    )
    client.get_offline_tasks = AsyncMock(
        return_value={
            "state": True,
            "tasks": [
                {
                    "info_hash": "task1_hash",
                    "name": "测试任务1",
                    "status": 2,
                    "percent_done": 100,
                    "add_time": 1700000000,
                },
                {
                    "info_hash": "task2_hash",
                    "name": "测试任务2",
                    "status": 0,
                    "percent_done": 50,
                    "add_time": 1700001000,
                },
            ],
        }
    )
    client.get_task_status = AsyncMock(
        return_value={
            "info_hash": "task1_hash",
            "name": "测试任务1",
            "status": 2,
            "percent_done": 100,
            "add_time": 1700000000,
        }
    )
    client.delete_offline_task = AsyncMock(return_value={"state": True})
    client.get_path_id = AsyncMock(return_value="123456")
    return client


@pytest.fixture
def mock_task_monitor():
    monitor = MagicMock()
    monitor._stop_event = MagicMock()
    monitor._stop_event.is_set = MagicMock(return_value=False)
    monitor._task = MagicMock()
    monitor._task.done = MagicMock(return_value=False)
    return monitor


@pytest.fixture
def test_app(mock_config, mock_p115_client, mock_task_monitor):
    app = FastAPI()

    init_tasks_router(mock_p115_client, mock_config)
    init_config_router(mock_config)
    init_system_router(mock_task_monitor, mock_p115_client)

    app.include_router(tasks.router, prefix="/api", tags=["tasks"])
    app.include_router(organize.router, prefix="/api", tags=["organize"])
    app.include_router(config.router, prefix="/api", tags=["config"])
    app.include_router(system.router, prefix="/api", tags=["system"])

    return app


@pytest_asyncio.fixture
async def client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestAddTask:
    @pytest.mark.asyncio
    async def test_add_task(self, client, mock_p115_client):
        response = await client.post(
            "/api/tasks",
            json={"magnet": "magnet:?xt=urn:btih:abc123", "library_name": "电影库"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "task_id" in data["data"]
        assert "message" in data

    @pytest.mark.asyncio
    async def test_add_task_invalid_library(self, client):
        response = await client.post(
            "/api/tasks",
            json={"magnet": "magnet:?xt=urn:btih:abc123", "library_name": "不存在的库"},
        )

        assert response.status_code == 404


class TestGetTasks:
    @pytest.mark.asyncio
    async def test_get_tasks(self, client, mock_p115_client):
        response = await client.get("/api/tasks")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "total" in data["data"]
        assert "tasks" in data["data"]
        assert isinstance(data["data"]["tasks"], list)


class TestGetTaskDetail:
    @pytest.mark.asyncio
    async def test_get_task_detail(self, client, mock_p115_client):
        response = await client.get("/api/tasks/task1_hash")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "task_id" in data["data"] or "info_hash" in data["data"]
        assert "name" in data["data"]

    @pytest.mark.asyncio
    async def test_get_task_detail_not_found(self, client, mock_p115_client):
        mock_p115_client.get_task_status = AsyncMock(return_value=None)

        response = await client.get("/api/tasks/nonexistent_hash")

        assert response.status_code == 404


class TestDeleteTask:
    @pytest.mark.asyncio
    async def test_delete_task(self, client, mock_p115_client):
        response = await client.delete("/api/tasks/task1_hash")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data


class TestGetOrganizeRecords:
    @pytest.mark.asyncio
    async def test_get_organize_records(self, client):
        with patch("app.api.organize.get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_count_result = MagicMock()
            mock_count_result.scalar.return_value = 0

            mock_records_result = MagicMock()
            mock_records_result.scalars.return_value.all.return_value = []

            mock_session.execute = AsyncMock(
                side_effect=[mock_count_result, mock_records_result]
            )

            mock_ctx = MagicMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_ctx

            response = await client.get("/api/organize/records")

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert "total" in data["data"]
            assert "records" in data["data"]


class TestGetConfig:
    @pytest.mark.asyncio
    async def test_get_config(self, client):
        response = await client.get("/api/config")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["message"] == "获取配置成功"
        assert "data" in data
        assert "p115" in data["data"]
        assert "media" in data["data"]


class TestUpdateConfig:
    @pytest.mark.asyncio
    async def test_update_config(self, client):
        response = await client.put(
            "/api/config",
            json={
                "p115": {
                    "rotation_training_interval_min": 70,
                    "rotation_training_interval_max": 90,
                }
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["message"] == "配置更新成功"
        assert "data" in data


class TestGetLibraries:
    @pytest.mark.asyncio
    async def test_get_libraries(self, client):
        response = await client.get("/api/libraries")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["message"] == "获取媒体库列表成功"
        assert "data" in data
        assert "libraries" in data["data"]
        assert isinstance(data["data"]["libraries"], list)
        assert len(data["data"]["libraries"]) == 2


class TestGetStatus:
    @pytest.mark.asyncio
    async def test_get_status(self, client):
        response = await client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["message"] == "获取系统状态成功"
        assert "data" in data
        assert "monitor_running" in data["data"]
        assert "active_tasks" in data["data"]
