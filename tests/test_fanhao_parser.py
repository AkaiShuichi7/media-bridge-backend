"""
@description 番号解析服务测试套件
@responsibility 验证番号提取、文件名标准化、目标路径生成等核心功能
"""

import pytest
from pathlib import Path


class TestRemoveKeywords:
    """测试关键词移除功能"""

    @pytest.mark.parametrize(
        "filename,keywords,expected",
        [
            # 基础移除
            ("hhd800.com@ABC-123.mp4", ["hhd800.com@"], "ABC-123.mp4"),
            # 多关键词
            (
                "hhd800.com@ABC-123_X1080X.mp4",
                ["hhd800.com@", "_X1080X"],
                "ABC-123.mp4",
            ),
            # 顺序无关
            ("ABC-123_X1080X[98t.tv].mp4", ["_X1080X", "[98t.tv]"], "ABC-123.mp4"),
            # 无匹配
            ("ABC-123.mp4", ["hhd800.com@"], "ABC-123.mp4"),
            # 空关键词
            ("ABC-123.mp4", [], "ABC-123.mp4"),
            # 特殊字符
            ("[98t.tv]ABC-123_60FPS.mp4", ["[98t.tv]", "_60FPS"], "ABC-123.mp4"),
            # 4k标记
            ("ABC-123-4k.mp4", ["-4k"], "ABC-123.mp4"),
            # 大小写敏感
            ("HHD800.COM@ABC-123.mp4", ["hhd800.com@"], "HHD800.COM@ABC-123.mp4"),
        ],
    )
    def test_remove_keywords(self, filename, keywords, expected):
        """验证关键词移除逻辑"""
        from app.services.fanhao_parser import remove_keywords

        assert remove_keywords(filename, keywords) == expected


class TestNormalizeFilename:
    """测试文件名标准化功能"""

    @pytest.mark.parametrize(
        "filename,expected",
        [
            # 小写转大写
            ("abc-123.mp4", "ABC-123.mp4"),
            # 点转横线（扩展名除外）
            ("ABC.123.mp4", "ABC-123.mp4"),
            # 混合情况
            ("abc.123.cd1.mp4", "ABC-123-CD1.mp4"),
            # 多个点
            ("abc.def.123.mp4", "ABC-DEF-123.mp4"),
            # 已经标准化
            ("ABC-123.mp4", "ABC-123.mp4"),
            # 保留扩展名的点
            ("abc-123.mkv", "ABC-123.mkv"),
            # 多扩展名（.tar.gz等特殊情况）
            ("abc-123.part1.mp4", "ABC-123-PART1.mp4"),
        ],
    )
    def test_normalize_filename(self, filename, expected):
        """验证文件名标准化逻辑"""
        from app.services.fanhao_parser import normalize_filename

        assert normalize_filename(filename) == expected


class TestExtractFanhao:
    """测试番号提取功能"""

    @pytest.mark.parametrize(
        "filename,expected",
        [
            # 标准格式
            ("ABC-123.mp4", "ABC-123"),
            ("SSNI-999.mp4", "SSNI-999"),
            # 带后缀
            ("ABC-123-CD1.mp4", "ABC-123"),
            ("ABC-123-C.mp4", "ABC-123"),
            # 长片商名
            ("ABCDEFGHIJ-12345.mp4", "ABCDEFGHIJ-12345"),
            # 短片商名
            ("AB-123.mp4", "AB-123"),
            # 最小编号
            ("ABC-001.mp4", "ABC-001"),
            # 复杂文件名
            ("hhd800.com@ABC-123_X1080X.mp4", "ABC-123"),
            # 无效格式（单字母片商）
            ("A-123.mp4", None),
            # 无效格式（编号过短）
            ("ABC-12.mp4", None),
            # 无效格式（编号过长）
            ("ABC-123456.mp4", None),
            # 无效格式（无横线）
            ("ABC123.mp4", None),
            # 多个匹配取第一个
            ("ABC-123-DEF-456.mp4", "ABC-123"),
        ],
    )
    def test_extract_fanhao(self, filename, expected):
        """验证番号提取逻辑，正则：[A-Z]{2,10}-\\d{3,5}"""
        from app.services.fanhao_parser import extract_fanhao

        assert extract_fanhao(filename) == expected


class TestCDSuffixMultiple:
    """测试多文件CD后缀处理"""

    @pytest.mark.parametrize(
        "filename,file_count,expected",
        [
            # -A/-B/-C 格式
            ("ABC-123-A.mp4", 2, "ABC-123-CD1.mp4"),
            ("ABC-123-B.mp4", 2, "ABC-123-CD2.mp4"),
            ("ABC-123-C.mp4", 3, "ABC-123-CD3.mp4"),
            # -1/-2/-3 格式
            ("ABC-123-1.mp4", 2, "ABC-123-CD1.mp4"),
            ("ABC-123-2.mp4", 2, "ABC-123-CD2.mp4"),
            # -PART1/-PART2 格式
            ("ABC-123-PART1.mp4", 2, "ABC-123-CD1.mp4"),
            ("ABC-123-PART2.mp4", 2, "ABC-123-CD2.mp4"),
            # 无后缀（多文件）
            ("ABC-123.mp4", 2, "ABC-123.mp4"),
            # 特殊标记（多文件时也转换）
            ("ABC-123-C.mp4", 2, "ABC-123-CD1.mp4"),  # -C 可能是 CD 标记
            ("ABC-123-U.mp4", 2, "ABC-123-CD1.mp4"),
        ],
    )
    def test_cd_suffix_multiple(self, filename, file_count, expected):
        """验证多文件时CD后缀标准化逻辑"""
        from app.services.fanhao_parser import normalize_cd_suffix

        assert normalize_cd_suffix(filename, file_count) == expected


class TestCDSuffixSingleSpecial:
    """测试单文件特殊标记保持"""

    @pytest.mark.parametrize(
        "filename,file_count,expected",
        [
            # 单文件 -C（Censored 有码）
            ("ABC-123-C.mp4", 1, "ABC-123-C.mp4"),
            # 单文件 -U（Uncensored 无码）
            ("ABC-123-U.mp4", 1, "ABC-123-U.mp4"),
            # 单文件 -UC
            ("ABC-123-UC.mp4", 1, "ABC-123-UC.mp4"),
            # 单文件 -CU
            ("ABC-123-CU.mp4", 1, "ABC-123-CU.mp4"),
            # 单文件无后缀
            ("ABC-123.mp4", 1, "ABC-123.mp4"),
            # 单文件其他后缀（不是特殊标记）
            ("ABC-123-A.mp4", 1, "ABC-123-A.mp4"),
        ],
    )
    def test_cd_suffix_single_special(self, filename, file_count, expected):
        """验证单文件时特殊标记保持不变"""
        from app.services.fanhao_parser import normalize_cd_suffix

        assert normalize_cd_suffix(filename, file_count) == expected


class TestGenerateTargetPath:
    """测试目标路径生成"""

    @pytest.mark.parametrize(
        "filename,target_dir,producer,expected",
        [
            # 标准格式
            ("ABC-123.mp4", "/media", "ABC", "/media/ABC/ABC-123/ABC-123.mp4"),
            # 带CD后缀
            ("ABC-123-CD1.mp4", "/media", "ABC", "/media/ABC/ABC-123/ABC-123-CD1.mp4"),
            # 不同扩展名
            ("SSNI-999.mkv", "/videos", "SSNI", "/videos/SSNI/SSNI-999/SSNI-999.mkv"),
            # 目标目录带尾部斜杠
            ("ABC-123.mp4", "/media/", "ABC", "/media/ABC/ABC-123/ABC-123.mp4"),
            # 长片商名
            (
                "ABCDEFGHIJ-12345.mp4",
                "/media",
                "ABCDEFGHIJ",
                "/media/ABCDEFGHIJ/ABCDEFGHIJ-12345/ABCDEFGHIJ-12345.mp4",
            ),
        ],
    )
    def test_generate_target_path(self, filename, target_dir, producer, expected):
        """验证目标路径生成逻辑：{target_dir}/{producer}/{fanhao}/{filename}"""
        from app.services.fanhao_parser import generate_target_path

        assert generate_target_path(filename, target_dir, producer) == expected


class TestExtractProducer:
    """测试片商名称提取"""

    @pytest.mark.parametrize(
        "library_type,expected",
        [
            # 标准格式
            ("xx-ABC", "ABC"),
            ("xx-SSNI", "SSNI"),
            # 长片商名
            ("xx-ABCDEFGHIJ", "ABCDEFGHIJ"),
            # system类型
            ("system", None),
            # 空字符串
            ("", None),
            # 无前缀
            ("ABC", None),
            # 仅xx前缀
            ("xx-", None),
        ],
    )
    def test_extract_producer(self, library_type, expected):
        """验证从library.type提取片商名称：xx-ABC → ABC"""
        from app.services.fanhao_parser import extract_producer

        assert extract_producer(library_type) == expected
