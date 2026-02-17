"""
@description 配置管理模块测试
@responsibility 验证配置加载、验证、环境变量覆盖功能
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.core.config import Config, load_config


class TestLoadConfigSuccess:
    """测试配置文件加载成功场景"""

    def test_load_config_success(self):
        """验证配置文件加载成功"""
        # 使用项目根目录的 config.yaml
        config = load_config()

        # 验证加载成功
        assert isinstance(config, Config)
        assert config.p115 is not None
        assert config.media is not None

        # 验证 p115 配置
        assert config.p115.cookies is not None
        assert config.p115.rotation_training_interval_min > 0
        assert config.p115.rotation_training_interval_max > 0

        # 验证 media 配置
        assert config.media.min_transfer_size > 0
        assert len(config.media.libraries) > 0
        assert len(config.media.video_formats) > 0

        # 验证第一个 library 配置
        lib = config.media.libraries[0]
        assert lib.name is not None
        assert lib.download_path is not None
        assert lib.target_path is not None
        assert lib.type is not None


class TestConfigNotExistsGenerateTemplate:
    """测试配置不存在时生成模板"""

    def test_config_not_exists_generate_template(self):
        """验证配置文件不存在时生成模板并抛出 SystemExit"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            template_path = Path(tmpdir) / "config.example.yaml"

            # 临时修改环境变量指向临时目录
            old_config_path = os.environ.get("CONFIG_PATH")
            try:
                os.environ["CONFIG_PATH"] = str(config_path)

                # 验证配置文件不存在时抛出 SystemExit
                with pytest.raises(SystemExit):
                    load_config()

                # 验证生成了模板文件
                assert template_path.exists(), "应生成 config.example.yaml"

                # 验证模板文件有效
                with open(template_path) as f:
                    content = yaml.safe_load(f)
                    assert "p115" in content
                    assert "media" in content
            finally:
                if old_config_path:
                    os.environ["CONFIG_PATH"] = old_config_path
                elif "CONFIG_PATH" in os.environ:
                    del os.environ["CONFIG_PATH"]


class TestEnvOverrideCookies:
    """测试环境变量覆盖 cookies"""

    def test_env_override_cookies(self):
        """验证 P115_COOKIES 环境变量覆盖配置中的 cookies"""
        test_cookies = "UID=test_uid; CID=test_cid; SEID=test_seid; KID=test_kid"

        old_cookies = os.environ.get("P115_COOKIES")
        try:
            os.environ["P115_COOKIES"] = test_cookies

            config = load_config()

            # 验证环境变量覆盖了配置文件中的 cookies
            assert config.p115.cookies == test_cookies
        finally:
            if old_cookies:
                os.environ["P115_COOKIES"] = old_cookies
            elif "P115_COOKIES" in os.environ:
                del os.environ["P115_COOKIES"]


class TestInvalidConfigValidation:
    """测试无效配置验证"""

    def test_invalid_config_validation(self):
        """验证无效配置触发 Pydantic ValidationError"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"

            # 创建无效配置（缺少必要字段）
            invalid_config = {
                "p115": {
                    # 缺少 cookies、rotation_training_interval_min、rotation_training_interval_max
                },
                "media": {
                    # 缺少 libraries、video_formats
                },
            }

            with open(config_path, "w") as f:
                yaml.dump(invalid_config, f)

            old_config_path = os.environ.get("CONFIG_PATH")
            try:
                os.environ["CONFIG_PATH"] = str(config_path)

                # 验证无效配置抛出 ValidationError
                with pytest.raises(ValidationError):
                    load_config()
            finally:
                if old_config_path:
                    os.environ["CONFIG_PATH"] = old_config_path
                elif "CONFIG_PATH" in os.environ:
                    del os.environ["CONFIG_PATH"]


class TestLibraryConfigValidation:
    """测试媒体库配置验证"""

    def test_library_config_structure(self):
        """验证媒体库配置结构"""
        config = load_config()

        # 验证 libraries 结构
        for lib in config.media.libraries:
            assert hasattr(lib, "name")
            assert hasattr(lib, "download_path")
            assert hasattr(lib, "target_path")
            assert hasattr(lib, "type")
            assert hasattr(lib, "min_transfer_size")


class TestXXConfigValidation:
    """测试 xx 配置验证"""

    def test_xx_config_structure(self):
        """验证 xx（成人片库）配置结构"""
        config = load_config()

        # 验证 xx 配置
        assert config.media.xx is not None
        assert hasattr(config.media.xx, "remove_keywords")
        assert isinstance(config.media.xx.remove_keywords, list)
        assert len(config.media.xx.remove_keywords) > 0
