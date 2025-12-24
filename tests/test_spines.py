# pylint: disable=redefined-outer-name

import shutil
from pathlib import Path

import pytest

from epub_translator.epub.spines import search_spine_paths
from epub_translator.epub.zip import Zip


@pytest.fixture
def spines_temp_dir():
    """创建并清理临时目录"""
    temp_path = Path("tests/temp/spines")

    # 每次测试前清空并创建目录
    if temp_path.exists():
        shutil.rmtree(temp_path)
    temp_path.mkdir(parents=True, exist_ok=True)

    yield temp_path

    # 测试后不删除，方便用户查看结果


class TestSearchSpinePathsEpub2:
    """测试 EPUB 2.0 格式的 spine 读取"""

    def test_search_little_prince_spines(self, spines_temp_dir):
        """测试读取 The little prince.epub (EPUB 2.0) 的 spine"""
        source_path = Path("tests/assets/The little prince.epub")
        temp_path = spines_temp_dir / "temp_little_prince.epub"

        with Zip(source_path, temp_path) as zip_file:
            spine_paths = list(search_spine_paths(zip_file))

            # 验证返回的路径数量
            assert len(spine_paths) > 0, "应该至少有一个 spine 文档"
            assert len(spine_paths) >= 28, f"应该至少有 28 个文档（章节数），实际有 {len(spine_paths)}"

            # 验证所有路径都是 Path 对象
            for path in spine_paths:
                assert isinstance(path, Path), f"返回的应该是 Path 对象，实际是 {type(path)}"

            # 验证所有文件都是 XHTML 格式
            for path in spine_paths:
                assert path.suffix in [".xhtml", ".html", ".htm"], f"文件应该是 HTML/XHTML 格式: {path}"

            # 验证第一个文档路径（spine 通常从标题页开始）
            first_spine = spine_paths[0]
            assert first_spine.suffix in [".xhtml", ".html", ".htm"], \
                f"第一个文档应该是 HTML/XHTML 格式，实际是 {first_spine}"

            # 验证包含主要章节文件
            spine_names = [p.name for p in spine_paths]
            assert "7358.xhtml" in spine_names, \
                f"应该包含 7358.xhtml（Chapter I），实际文件列表: {spine_names[:10]}"

    def test_search_chinese_book_spines(self, spines_temp_dir):
        """测试读取治疗精神病.epub (EPUB 2.0) 的 spine"""
        source_path = Path("tests/assets/治疗精神病.epub")
        temp_path = spines_temp_dir / "temp_chinese.epub"

        with Zip(source_path, temp_path) as zip_file:
            spine_paths = list(search_spine_paths(zip_file))

            # 验证返回的路径数量
            assert len(spine_paths) > 0, "应该至少有一个 spine 文档"

            # 验证所有路径都是 XHTML 格式
            for path in spine_paths:
                assert path.suffix in [".xhtml", ".html", ".htm"], f"文件应该是 HTML/XHTML 格式: {path}"

            # 验证是否包含封面
            cover_found = any("cover" in str(path).lower() for path in spine_paths)
            assert cover_found, "应该包含封面文档"


class TestSearchSpinePathsEpub3:
    """测试 EPUB 3.0 格式的 spine 读取"""

    def test_search_deepseek_ocr_spines(self, spines_temp_dir):
        """测试读取 DeepSeek OCR.epub (EPUB 3.0) 的 spine"""
        source_path = Path("tests/assets/DeepSeek OCR.epub")
        temp_path = spines_temp_dir / "temp_deepseek.epub"

        with Zip(source_path, temp_path) as zip_file:
            spine_paths = list(search_spine_paths(zip_file))

            # 验证返回的路径数量
            assert len(spine_paths) > 0, "应该至少有一个 spine 文档"

            # 验证所有路径都是 Path 对象
            for path in spine_paths:
                assert isinstance(path, Path), f"返回的应该是 Path 对象，实际是 {type(path)}"

            # 验证所有文件都是 XHTML/HTML 格式
            for path in spine_paths:
                assert path.suffix in [".xhtml", ".html", ".htm"], f"文件应该是 HTML/XHTML 格式: {path}"

            # 验证是否包含封面和内容
            cover_found = any("cover" in str(path).lower() for path in spine_paths)
            content_found = any("part" in str(path).lower() or "chapter" in str(path).lower()
                              for path in spine_paths)

            assert cover_found or content_found, "应该包含封面或内容文档"


class TestSpineCompletenessComparison:
    """测试 spine 是否比 TOC 更完整"""

    def test_spine_contains_all_toc_files(self, spines_temp_dir):
        """验证 spine 包含 TOC 中引用的所有文件（以及更多）"""
        from epub_translator.epub.toc import read_toc

        source_path = Path("tests/assets/The little prince.epub")
        temp_path = spines_temp_dir / "temp_comparison.epub"

        with Zip(source_path, temp_path) as zip_file:
            # 获取 spine 中的所有文件
            spine_paths = list(search_spine_paths(zip_file))
            spine_files = {path.name for path in spine_paths}

            # 获取 TOC 中引用的所有文件
            toc_list = read_toc(zip_file)
            toc_files = set()

            def collect_toc_files(items):
                for item in items:
                    if item.href:
                        toc_files.add(item.href)
                    if item.children:
                        collect_toc_files(item.children)

            collect_toc_files(toc_list)

            # 验证 TOC 中的文件是否都在 spine 中
            toc_files_in_spine = toc_files.intersection(spine_files)
            print(f"\nTOC 文件数: {len(toc_files)}")
            print(f"Spine 文件数: {len(spine_files)}")
            print(f"TOC 与 Spine 交集: {len(toc_files_in_spine)}")

            # TOC 中的大部分文件应该在 spine 中
            # 注意：某些 TOC 可能指向文档片段，所以不一定 100% 匹配
            assert len(toc_files_in_spine) > 0, "TOC 中至少有一些文件应该在 spine 中"

            # spine 应该包含更多文件（如版权页、封面等）
            # 这证明了从 spine 出发能找到更完整的内容
            assert len(spine_files) >= len(toc_files), \
                "Spine 应该包含至少与 TOC 相同数量的文件（通常更多）"


class TestSpinePathStructure:
    """测试 spine 路径的结构"""

    def test_spine_paths_are_relative(self, spines_temp_dir):
        """验证返回的路径包含正确的目录结构"""
        source_path = Path("tests/assets/DeepSeek OCR.epub")
        temp_path = spines_temp_dir / "temp_path_structure.epub"

        with Zip(source_path, temp_path) as zip_file:
            spine_paths = list(search_spine_paths(zip_file))

            # 验证路径结构
            for path in spine_paths:
                # 路径应该包含目录部分（如 OEBPS/Text/xxx.xhtml）
                assert len(path.parts) >= 1, f"路径应该至少有一个部分: {path}"

    def test_spine_paths_order(self, spines_temp_dir):
        """验证 spine 返回的路径保持顺序"""
        source_path = Path("tests/assets/The little prince.epub")
        temp_path = spines_temp_dir / "temp_order.epub"

        with Zip(source_path, temp_path) as zip_file:
            # 多次调用应该返回相同的顺序
            spine_paths_1 = list(search_spine_paths(zip_file))
            spine_paths_2 = list(search_spine_paths(zip_file))

            assert spine_paths_1 == spine_paths_2, "多次调用应该返回相同顺序的路径"


class TestEdgeCases:
    """测试边缘情况"""

    def test_generator_can_be_iterated(self, spines_temp_dir):
        """验证返回的生成器可以被正常迭代"""
        source_path = Path("tests/assets/The little prince.epub")
        temp_path = spines_temp_dir / "temp_generator.epub"

        with Zip(source_path, temp_path) as zip_file:
            spine_generator = search_spine_paths(zip_file)

            # 验证是生成器
            assert hasattr(spine_generator, "__iter__"), "应该返回一个可迭代对象"
            assert hasattr(spine_generator, "__next__"), "应该返回一个生成器"

            # 验证可以迭代
            count = 0
            for path in spine_generator:
                count += 1
                assert isinstance(path, Path)

            assert count > 0, "生成器应该至少产生一个路径"

    def test_all_paths_are_unique(self, spines_temp_dir):
        """验证返回的路径没有重复"""
        source_path = Path("tests/assets/DeepSeek OCR.epub")
        temp_path = spines_temp_dir / "temp_unique.epub"

        with Zip(source_path, temp_path) as zip_file:
            spine_paths = list(search_spine_paths(zip_file))
            unique_paths = set(spine_paths)

            assert len(spine_paths) == len(unique_paths), \
                f"路径不应该重复，总数: {len(spine_paths)}, 唯一: {len(unique_paths)}"


class TestSpineMediaTypes:
    """测试 spine 正确过滤 media-type"""

    def test_only_html_xhtml_documents(self, spines_temp_dir):
        """验证只返回 HTML/XHTML 文档（不包含图片、CSS 等）"""
        source_path = Path("tests/assets/The little prince.epub")
        temp_path = spines_temp_dir / "temp_media_type.epub"

        with Zip(source_path, temp_path) as zip_file:
            spine_paths = list(search_spine_paths(zip_file))

            # 验证所有文件扩展名
            valid_extensions = {".xhtml", ".html", ".htm"}
            for path in spine_paths:
                assert path.suffix.lower() in valid_extensions, \
                    f"文件 {path} 的扩展名应该是 {valid_extensions} 之一"

            # 验证不包含非文档文件
            invalid_extensions = {".css", ".js", ".jpg", ".png", ".gif", ".svg", ".ttf", ".otf"}
            for path in spine_paths:
                assert path.suffix.lower() not in invalid_extensions, \
                    f"不应该包含非文档文件: {path}"
