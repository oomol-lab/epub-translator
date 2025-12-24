# pylint: disable=redefined-outer-name

import shutil
from pathlib import Path

import pytest

from epub_translator.epub.toc import Toc, read_toc, write_toc
from epub_translator.epub.zip import Zip


@pytest.fixture
def toc_temp_dir():
    """创建并清理临时目录"""
    temp_path = Path("tests/temp/toc")

    # 每次测试前清空并创建目录
    if temp_path.exists():
        shutil.rmtree(temp_path)
    temp_path.mkdir(parents=True, exist_ok=True)

    yield temp_path

    # 测试后不删除，方便用户查看结果


class TestReadTocEpub2:
    """测试 EPUB 2.0 格式的目录读取"""

    def test_read_little_prince_toc(self, toc_temp_dir):
        """测试读取 The little prince.epub (EPUB 2.0) 的目录"""
        source_path = Path("tests/assets/The little prince.epub")
        temp_path = toc_temp_dir / "temp_little_prince.epub"

        with Zip(source_path, temp_path) as zip_file:
            toc_list = read_toc(zip_file)

            # 验证读取到的目录项数量
            assert len(toc_list) == 28, "应该有 28 个顶层目录项"

            # 验证第一个目录项
            first_item = toc_list[0]
            assert first_item.title == "Chapter I"
            assert first_item.href == "7358.xhtml"
            assert first_item.id == "0"
            assert first_item.fragment is None
            assert len(first_item.children) == 0

            # 验证最后一个目录项（带锚点）
            last_item = toc_list[-1]
            assert last_item.title == "Saint-Exupéry: A Short Biography"
            assert last_item.href == "10740.xhtml"
            assert last_item.fragment == "10664"
            assert last_item.full_href == "10740.xhtml#10664"
            assert last_item.id == "27"

    def test_read_chinese_book_toc(self, toc_temp_dir):
        """测试读取治疗精神病.epub (EPUB 2.0) 的目录"""
        source_path = Path("tests/assets/治疗精神病.epub")
        temp_path = toc_temp_dir / "temp_chinese.epub"

        with Zip(source_path, temp_path) as zip_file:
            toc_list = read_toc(zip_file)

            # 验证读取到的目录项数量
            assert len(toc_list) == 1, "应该只有 1 个顶层目录项"

            # 验证目录项
            item = toc_list[0]
            assert item.title == "封面"
            assert item.href == "Text/cover.xhtml"
            assert item.id == "cover"
            assert len(item.children) == 0


class TestReadTocEpub3:
    """测试 EPUB 3.0 格式的目录读取"""

    def test_read_deepseek_ocr_toc(self, toc_temp_dir):
        """测试读取 DeepSeek OCR.epub (EPUB 3.0) 的目录"""
        source_path = Path("tests/assets/DeepSeek OCR.epub")
        temp_path = toc_temp_dir / "temp_deepseek.epub"

        with Zip(source_path, temp_path) as zip_file:
            toc_list = read_toc(zip_file)

            # 验证读取到的目录项数量
            assert len(toc_list) == 2, "应该有 2 个顶层目录项"

            # 验证第一个目录项
            first_item = toc_list[0]
            assert first_item.title == "封面"
            assert first_item.href == "Text/cover.xhtml"

            # 验证第二个目录项及其子节点
            second_item = toc_list[1]
            assert second_item.title == "DeepSeek-OCR: Contexts Optical Compression"
            assert second_item.href == "Text/part01.xhtml"
            assert len(second_item.children) > 0, "第二个目录项应该有子节点"

            # 验证子节点
            first_child = second_item.children[0]
            assert first_child.title == "Abstract"
            assert first_child.href == "Text/part02.xhtml"


class TestWriteTocEpub2:
    """测试 EPUB 2.0 格式的目录写入"""

    def test_write_modified_toc_little_prince(self, toc_temp_dir):
        """测试修改并写回 The little prince.epub 的目录"""
        source_path = Path("tests/assets/The little prince.epub")
        output_path = toc_temp_dir / "modified_little_prince.epub"

        # 读取原始目录
        with Zip(source_path, output_path) as zip_file:
            toc_list = read_toc(zip_file)

            # 修改目录项标题
            for item in toc_list:
                item.title = f"[Modified] {item.title}"

            # 写回修改后的目录
            write_toc(zip_file, toc_list)

        # 验证修改是否成功
        with Zip(output_path, toc_temp_dir / "verify_little_prince.epub") as zip_file:
            modified_toc = read_toc(zip_file)

            assert len(modified_toc) == len(toc_list)
            assert modified_toc[0].title == "[Modified] Chapter I"
            assert modified_toc[-1].title == "[Modified] Saint-Exupéry: A Short Biography"

            # 验证其他属性没有改变
            assert modified_toc[0].href == "7358.xhtml"
            assert modified_toc[0].id == "0"
            assert modified_toc[-1].href == "10740.xhtml"
            assert modified_toc[-1].fragment == "10664"

    def test_add_new_toc_item(self, toc_temp_dir):
        """测试添加新的目录项"""
        source_path = Path("tests/assets/治疗精神病.epub")
        output_path = toc_temp_dir / "added_item_chinese.epub"

        # 读取原始目录
        with Zip(source_path, output_path) as zip_file:
            toc_list = read_toc(zip_file)

            # 添加新的目录项
            new_item = Toc(
                title="新增章节",
                href="Text/new_chapter.xhtml",
                fragment=None,
                id="new-chapter",
                children=[],
            )
            toc_list.append(new_item)

            # 写回修改后的目录
            write_toc(zip_file, toc_list)

        # 验证添加是否成功
        with Zip(output_path, toc_temp_dir / "verify_chinese.epub") as zip_file:
            modified_toc = read_toc(zip_file)

            assert len(modified_toc) == 2, "应该有 2 个顶层目录项"
            assert modified_toc[0].title == "封面"
            assert modified_toc[1].title == "新增章节"
            assert modified_toc[1].href == "Text/new_chapter.xhtml"
            assert modified_toc[1].id == "new-chapter"

    def test_remove_toc_item(self, toc_temp_dir):
        """测试删除目录项"""
        source_path = Path("tests/assets/The little prince.epub")
        output_path = toc_temp_dir / "removed_items_little_prince.epub"

        # 读取原始目录
        with Zip(source_path, output_path) as zip_file:
            toc_list = read_toc(zip_file)
            original_count = len(toc_list)

            # 删除前 3 个目录项
            toc_list = toc_list[3:]

            # 写回修改后的目录
            write_toc(zip_file, toc_list)

        # 验证删除是否成功
        with Zip(output_path, toc_temp_dir / "verify_removed.epub") as zip_file:
            modified_toc = read_toc(zip_file)

            assert len(modified_toc) == original_count - 3
            assert modified_toc[0].title == "Chapter IV"
            assert modified_toc[0].id == "3"


class TestWriteTocEpub3:
    """测试 EPUB 3.0 格式的目录写入"""

    def test_write_modified_toc_deepseek(self, toc_temp_dir):
        """测试修改并写回 DeepSeek OCR.epub 的目录"""
        source_path = Path("tests/assets/DeepSeek OCR.epub")
        output_path = toc_temp_dir / "modified_deepseek.epub"

        # 读取原始目录
        with Zip(source_path, output_path) as zip_file:
            toc_list = read_toc(zip_file)

            # 递归修改所有目录项标题
            def modify_titles(items):
                for item in items:
                    item.title = f"【译】{item.title}"
                    if item.children:
                        modify_titles(item.children)

            modify_titles(toc_list)

            # 写回修改后的目录
            write_toc(zip_file, toc_list)

        # 验证修改是否成功
        with Zip(output_path, toc_temp_dir / "verify_deepseek.epub") as zip_file:
            modified_toc = read_toc(zip_file)

            assert len(modified_toc) == 2
            assert modified_toc[0].title == "【译】封面"
            assert modified_toc[1].title == "【译】DeepSeek-OCR: Contexts Optical Compression"

            # 验证子节点也被修改
            if modified_toc[1].children:
                assert modified_toc[1].children[0].title == "【译】Abstract"

    def test_add_nested_toc_items(self, toc_temp_dir):
        """测试添加嵌套的目录项"""
        source_path = Path("tests/assets/DeepSeek OCR.epub")
        output_path = toc_temp_dir / "nested_deepseek.epub"

        # 读取原始目录
        with Zip(source_path, output_path) as zip_file:
            toc_list = read_toc(zip_file)

            # 添加一个带子节点的新目录项
            new_parent = Toc(
                title="附录",
                href="Text/appendix.xhtml",
                fragment=None,
                id="appendix",
                children=[
                    Toc(title="附录 A", href="Text/appendix_a.xhtml", id="appendix-a"),
                    Toc(title="附录 B", href="Text/appendix_b.xhtml", id="appendix-b"),
                ],
            )
            toc_list.append(new_parent)

            # 写回修改后的目录
            write_toc(zip_file, toc_list)

        # 验证添加是否成功
        with Zip(output_path, toc_temp_dir / "verify_nested.epub") as zip_file:
            modified_toc = read_toc(zip_file)

            assert len(modified_toc) == 3, "应该有 3 个顶层目录项"
            new_item = modified_toc[-1]
            assert new_item.title == "附录"
            assert len(new_item.children) == 2
            assert new_item.children[0].title == "附录 A"
            assert new_item.children[1].title == "附录 B"


class TestTocDataClass:
    """测试 Toc 数据类的功能"""

    def test_full_href_with_fragment(self):
        """测试带锚点的 full_href"""
        toc = Toc(title="Test", href="chapter.xhtml", fragment="section1", id="test-1")
        assert toc.full_href == "chapter.xhtml#section1"

    def test_full_href_without_fragment(self):
        """测试不带锚点的 full_href"""
        toc = Toc(title="Test", href="chapter.xhtml", fragment=None, id="test-2")
        assert toc.full_href == "chapter.xhtml"

    def test_full_href_with_none_href(self):
        """测试 href 为 None 的情况"""
        toc = Toc(title="Test", href=None, fragment=None, id="test-3")
        assert toc.full_href is None

    def test_nested_children(self):
        """测试嵌套的子节点结构"""
        child2 = Toc(title="Child 2", href="child2.xhtml")
        child1 = Toc(title="Child 1", href="child1.xhtml", children=[child2])
        parent = Toc(title="Parent", href="parent.xhtml", children=[child1])

        assert len(parent.children) == 1
        assert parent.children[0].title == "Child 1"
        assert len(parent.children[0].children) == 1
        assert parent.children[0].children[0].title == "Child 2"


class TestEdgeCases:
    """测试边缘情况"""

    def test_empty_toc_list(self, toc_temp_dir):
        """测试空目录列表的写入"""
        source_path = Path("tests/assets/治疗精神病.epub")
        output_path = toc_temp_dir / "empty_toc.epub"

        # 读取原始目录
        with Zip(source_path, output_path) as zip_file:
            # 写入空目录列表
            write_toc(zip_file, [])

        # 验证空目录
        with Zip(output_path, toc_temp_dir / "verify_empty.epub") as zip_file:
            toc_list = read_toc(zip_file)
            assert len(toc_list) == 0, "目录应该为空"

    def test_toc_with_special_characters(self, toc_temp_dir):
        """测试包含特殊字符的目录项"""
        source_path = Path("tests/assets/治疗精神病.epub")
        output_path = toc_temp_dir / "special_chars.epub"

        special_title = "Chapter <1> & \"Quotes\" & 'Apostrophes' & 测试"

        with Zip(source_path, output_path) as zip_file:
            toc_list = [
                Toc(
                    title=special_title,
                    href="Text/special.xhtml",
                    id="special-1",
                )
            ]
            write_toc(zip_file, toc_list)

        # 验证特殊字符是否正确保存
        with Zip(output_path, toc_temp_dir / "verify_special.epub") as zip_file:
            modified_toc = read_toc(zip_file)
            assert len(modified_toc) == 1
            # XML 会转义特殊字符，但读取时会还原
            assert modified_toc[0].title == special_title

    def test_toc_without_href(self, toc_temp_dir):
        """测试没有链接的目录项（纯分组节点）- 使用 EPUB 3"""
        source_path = Path("tests/assets/DeepSeek OCR.epub")
        output_path = toc_temp_dir / "no_href.epub"

        with Zip(source_path, output_path) as zip_file:
            toc_list = [
                Toc(
                    title="第一部分",
                    href=None,  # 没有链接，纯分组
                    id="part-1",
                    children=[
                        Toc(title="第一章", href="Text/chapter1.xhtml", id="ch-1"),
                        Toc(title="第二章", href="Text/chapter2.xhtml", id="ch-2"),
                    ],
                )
            ]
            write_toc(zip_file, toc_list)

        # 验证纯分组节点
        with Zip(output_path, toc_temp_dir / "verify_no_href.epub") as zip_file:
            modified_toc = read_toc(zip_file)
            assert len(modified_toc) == 1
            assert modified_toc[0].title == "第一部分"
            assert modified_toc[0].href is None
            assert modified_toc[0].full_href is None
            assert len(modified_toc[0].children) == 2


class TestRoundTrip:
    """测试完整的读写往返"""

    def test_roundtrip_epub2(self, toc_temp_dir):
        """测试 EPUB 2 的完整读写往返（不修改内容）"""
        source_path = Path("tests/assets/The little prince.epub")
        output_path = toc_temp_dir / "roundtrip_epub2.epub"

        # 第一次读取
        with Zip(source_path, output_path) as zip_file:
            original_toc = read_toc(zip_file)
            write_toc(zip_file, original_toc)

        # 第二次读取，验证一致性
        with Zip(output_path, toc_temp_dir / "roundtrip_epub2_verify.epub") as zip_file:
            roundtrip_toc = read_toc(zip_file)

            assert len(roundtrip_toc) == len(original_toc)
            for orig, rt in zip(original_toc, roundtrip_toc):
                assert orig.title == rt.title
                assert orig.href == rt.href
                assert orig.fragment == rt.fragment
                assert orig.id == rt.id

    def test_roundtrip_epub3(self, toc_temp_dir):
        """测试 EPUB 3 的完整读写往返（不修改内容）"""
        source_path = Path("tests/assets/DeepSeek OCR.epub")
        output_path = toc_temp_dir / "roundtrip_epub3.epub"

        # 第一次读取
        with Zip(source_path, output_path) as zip_file:
            original_toc = read_toc(zip_file)
            write_toc(zip_file, original_toc)

        # 第二次读取，验证一致性
        with Zip(output_path, toc_temp_dir / "roundtrip_epub3_verify.epub") as zip_file:
            roundtrip_toc = read_toc(zip_file)

            def compare_toc_recursive(orig_list, rt_list):
                assert len(orig_list) == len(rt_list)
                for orig, rt in zip(orig_list, rt_list):
                    assert orig.title == rt.title
                    assert orig.href == rt.href
                    assert orig.fragment == rt.fragment
                    # ID 可能在写入时改变（如果原来没有），所以不严格比较
                    if orig.children:
                        compare_toc_recursive(orig.children, rt.children)

            compare_toc_recursive(original_toc, roundtrip_toc)
