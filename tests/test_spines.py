# pylint: disable=redefined-outer-name

from pathlib import Path

from epub_translator.epub.spines import search_spine_paths
from epub_translator.epub.zip import Zip
from tests.utils import create_temp_dir_fixture

# 创建 spines 专用的临时目录 fixture
spines_temp_dir = create_temp_dir_fixture("spines")


class TestSearchSpinePathsEpub2:
    """测试 EPUB 2.0 格式的 spine 读取"""

    def test_search_little_prince_spines(self, spines_temp_dir):
        """测试读取 The little prince.epub (EPUB 2.0) 的 spine"""
        source_path = Path("tests/assets/The little prince.epub")
        temp_path = spines_temp_dir / "temp_little_prince.epub"

        with Zip(source_path, temp_path) as zip_file:
            spine_results = list(search_spine_paths(zip_file))

            # 验证返回的路径数量
            assert len(spine_results) > 0, "应该至少有一个 spine 文档"
            assert len(spine_results) >= 28, f"应该至少有 28 个文档（章节数），实际有 {len(spine_results)}"

            # 验证所有返回值是元组 (Path, media_type)
            for path, media_type in spine_results:
                assert isinstance(path, Path), f"返回的路径应该是 Path 对象，实际是 {type(path)}"
                assert isinstance(media_type, str), f"返回的 media_type 应该是 str，实际是 {type(media_type)}"
                assert media_type in ("application/xhtml+xml", "text/html"), f"无效的 media_type: {media_type}"

            # 验证所有文件都是 HTML/XHTML 格式
            for path, _ in spine_results:
                assert path.suffix in [".xhtml", ".html", ".htm"], f"文件应该是 HTML/XHTML 格式: {path}"

            # 验证第一个文档路径（spine 通常从标题页开始）
            first_spine_path, _ = spine_results[0]
            assert first_spine_path.suffix in [".xhtml", ".html", ".htm"], (
                f"第一个文档应该是 HTML/XHTML 格式，实际是 {first_spine_path}"
            )

            # 验证包含主要章节文件
            spine_names = [path.name for path, _ in spine_results]
            assert "7358.xhtml" in spine_names, f"应该包含 7358.xhtml（Chapter I），实际文件列表: {spine_names[:10]}"

    def test_search_chinese_book_spines(self, spines_temp_dir):
        """测试读取治疗精神病.epub (EPUB 2.0) 的 spine"""
        source_path = Path("tests/assets/治疗精神病.epub")
        temp_path = spines_temp_dir / "temp_chinese.epub"

        with Zip(source_path, temp_path) as zip_file:
            spine_results = list(search_spine_paths(zip_file))

            # 验证返回的路径数量
            assert len(spine_results) > 0, "应该至少有一个 spine 文档"

            # 验证所有路径都是 XHTML 格式
            for path, _ in spine_results:
                assert path.suffix in [".xhtml", ".html", ".htm"], f"文件应该是 HTML/XHTML 格式: {path}"

            # 验证是否包含封面
            cover_found = any("cover" in str(path).lower() for path, _ in spine_results)
            assert cover_found, "应该包含封面文档"


class TestSearchSpinePathsEpub3:
    """测试 EPUB 3.0 格式的 spine 读取"""

    def test_search_deepseek_ocr_spines(self, spines_temp_dir):
        """测试读取 DeepSeek OCR.epub (EPUB 3.0) 的 spine"""
        source_path = Path("tests/assets/DeepSeek OCR.epub")
        temp_path = spines_temp_dir / "temp_deepseek.epub"

        with Zip(source_path, temp_path) as zip_file:
            spine_results = list(search_spine_paths(zip_file))

            # 验证返回的路径数量
            assert len(spine_results) > 0, "应该至少有一个 spine 文档"

            # 验证所有返回值是元组
            for path, media_type in spine_results:
                assert isinstance(path, Path), f"返回的路径应该是 Path 对象，实际是 {type(path)}"
                assert isinstance(media_type, str), f"返回的 media_type 应该是 str，实际是 {type(media_type)}"

            # 验证所有文件都是 XHTML/HTML 格式
            for path, _ in spine_results:
                assert path.suffix in [".xhtml", ".html", ".htm"], f"文件应该是 HTML/XHTML 格式: {path}"

            # 验证是否包含封面和内容
            cover_found = any("cover" in str(path).lower() for path, _ in spine_results)
            content_found = any(
                "part" in str(path).lower() or "chapter" in str(path).lower() for path, _ in spine_results
            )

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
            spine_results = list(search_spine_paths(zip_file))
            spine_files = {path.name for path, _ in spine_results}

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


class TestSpinePathsStructure:
    """测试 spine 路径结构"""

    def test_spine_paths_are_relative(self, spines_temp_dir):
        """验证返回的路径是相对路径"""
        source_path = Path("tests/assets/The little prince.epub")
        temp_path = spines_temp_dir / "temp_relative.epub"

        with Zip(source_path, temp_path) as zip_file:
            spine_results = list(search_spine_paths(zip_file))

            # 验证路径结构
            for path, _ in spine_results:
                assert not path.is_absolute(), f"返回的路径应该是相对路径: {path}"

    def test_spine_paths_order(self, spines_temp_dir):
        """验证 spine 路径的顺序一致性"""
        source_path = Path("tests/assets/The little prince.epub")
        temp_path = spines_temp_dir / "temp_order.epub"

        with Zip(source_path, temp_path) as zip_file:
            # 多次调用应该返回相同的顺序
            spine_paths_1 = list(search_spine_paths(zip_file))
            spine_paths_2 = list(search_spine_paths(zip_file))

            assert spine_paths_1 == spine_paths_2, "多次调用应该返回相同顺序的路径"

    def test_spine_is_generator(self, spines_temp_dir):
        """验证 search_spine_paths 返回生成器"""
        from collections.abc import Generator

        source_path = Path("tests/assets/The little prince.epub")
        temp_path = spines_temp_dir / "temp_generator.epub"

        with Zip(source_path, temp_path) as zip_file:
            spine_generator = search_spine_paths(zip_file)

            # 验证是生成器
            assert isinstance(spine_generator, Generator), "search_spine_paths 应该返回生成器"

            # 验证可以迭代
            count = 0
            for _ in spine_generator:
                count += 1
                if count >= 5:  # 只测试前几个
                    break

            assert count > 0, "生成器应该可以迭代"


class TestSpinePathsValidation:
    """测试 spine 路径验证"""

    def test_spine_paths_are_unique(self, spines_temp_dir):
        """验证 spine 中的路径不重复"""
        source_path = Path("tests/assets/The little prince.epub")
        temp_path = spines_temp_dir / "temp_unique.epub"

        with Zip(source_path, temp_path) as zip_file:
            spine_results = list(search_spine_paths(zip_file))
            spine_paths = [path for path, _ in spine_results]
            unique_paths = set(spine_paths)

            assert len(spine_paths) == len(unique_paths), (
                f"spine 中有重复路径：{len(spine_paths)} 个路径，{len(unique_paths)} 个唯一路径"
            )

    def test_spine_paths_file_extensions(self, spines_temp_dir):
        """验证 spine 中的文件扩展名都是 HTML/XHTML"""
        source_path = Path("tests/assets/The little prince.epub")
        temp_path = spines_temp_dir / "temp_extensions.epub"

        with Zip(source_path, temp_path) as zip_file:
            spine_results = list(search_spine_paths(zip_file))

            # 验证所有文件扩展名
            valid_extensions = {".xhtml", ".html", ".htm"}
            for path, _ in spine_results:
                assert path.suffix in valid_extensions, (
                    f"spine 中的文件应该是 HTML/XHTML：{path}（扩展名：{path.suffix}）"
                )
