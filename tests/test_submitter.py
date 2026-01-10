import unittest
from xml.etree.ElementTree import Element, fromstring, tostring

from epub_translator.segment import search_text_segments
from epub_translator.utils import normalize_whitespace
from epub_translator.xml import iter_with_stack
from epub_translator.xml_translator.stream_mapper import InlineSegmentMapping
from epub_translator.xml_translator.submitter import SubmitKind, submit


def parse_xml(xml_str: str) -> Element:
    """解析 XML 字符串为 Element"""
    return fromstring(xml_str.strip())


def element_to_string(element: Element) -> str:
    """将 Element 转换为字符串，便于比较"""
    result = tostring(element, encoding="unicode", method="html")
    # 移除末尾的换行符
    return result.rstrip()


def find_element_by_id(root: Element, element_id: str) -> Element:
    """通过 id 属性查找元素"""
    for _, elem in iter_with_stack(root):
        if elem.get("id") == element_id:
            return elem
    raise ValueError(f"Cannot find element with id={element_id}")


class TestSubmitReplace(unittest.TestCase):
    """测试 REPLACE 模式"""

    def test_replace_peak_simple(self):
        """测试 REPLACE 模式 - 简单 Peak 结构"""
        xml_str = """
        <div>
            <p id="p1">hello world</p>
        </div>
        """
        root = parse_xml(xml_str)
        p1 = find_element_by_id(root, "p1")

        # 构造译文并提取 TextSegments
        translated_xml = parse_xml("<span>你好世界</span>")
        translated_segments = list(search_text_segments(translated_xml))

        mappings: list[InlineSegmentMapping] = [(p1, translated_segments)]

        result = submit(root, SubmitKind.REPLACE, mappings)
        result_str = element_to_string(result)

        expected = """
            <div>
                <span>你好世界</span>
            </div>
        """
        self.assertEqual(normalize_whitespace(result_str).strip(), normalize_whitespace(expected).strip())

    def test_replace_peak_with_inline_tags(self):
        """测试 REPLACE 模式 - Peak 结构，删除 inline 标签"""
        xml_str = """
        <div>
            <p id="p1">hello <span>world</span> abc</p>
            <p id="p2">next paragraph</p>
        </div>
        """
        root = parse_xml(xml_str)
        p1 = find_element_by_id(root, "p1")

        # 构造译文并提取 TextSegments
        translated_xml = parse_xml("<span>你好世界一二三</span>")
        translated_segments = list(search_text_segments(translated_xml))

        mappings: list[InlineSegmentMapping] = [(p1, translated_segments)]

        result = submit(root, SubmitKind.REPLACE, mappings)
        result_str = element_to_string(result)

        expected = """
            <div>
                <span>你好世界一二三</span>
                <p id="p2">next paragraph</p>
            </div>
        """
        self.assertEqual(normalize_whitespace(result_str).strip(), normalize_whitespace(expected).strip())

    def test_replace_with_preserved_non_inline_tags(self):
        """测试 REPLACE 模式 - 保留非 inline 标签（如 <image>）"""
        xml_str = """
        <div>
            <div id="d1">
                hello world
                <image src="test.png" />
                something
            </div>
        </div>
        """
        root = parse_xml(xml_str)
        d1 = find_element_by_id(root, "d1")

        # 构造译文：将两部分文本合并翻译
        # 使用 <br/> 分隔，以便 search_text_segments 能提取出两个 segment
        translated_xml = parse_xml("<div>你好世界<br />某些东西</div>")
        translated_segments = list(search_text_segments(translated_xml))

        mappings: list[InlineSegmentMapping] = [(d1, translated_segments)]

        result = submit(root, SubmitKind.REPLACE, mappings)
        result_str = element_to_string(result)

        expected = """
            <div>
                <div>你好世界某些东西</div><image src="test.png"></image>
            </div>
        """
        self.assertEqual(normalize_whitespace(result_str).strip(), normalize_whitespace(expected).strip())

    def test_replace_platform_structure(self):
        """测试 REPLACE 模式 - Platform 结构"""
        xml_str = """
        <div>
            <div id="d1">
                hello world
                <div id="d2">sub block</div>
                something
            </div>
        </div>
        """
        root = parse_xml(xml_str)
        d1 = find_element_by_id(root, "d1")
        d2 = find_element_by_id(root, "d2")

        # 构造译文 - d1 的第一部分（hello world）
        trans1_xml = parse_xml("<span>你好世界</span>")
        trans1_segments = list(search_text_segments(trans1_xml))

        # 构造译文 - d2（sub block）
        trans2_xml = parse_xml("<span>子块</span>")
        trans2_segments = list(search_text_segments(trans2_xml))

        # 构造译文 - d1 的第二部分（something）
        trans3_xml = parse_xml("<span>某些东西</span>")
        trans3_segments = list(search_text_segments(trans3_xml))

        # d1 是 platform 结构，包含 d2 作为子节点
        mappings: list[InlineSegmentMapping] = [
            (d1, trans1_segments),  # hello world 部分
            (d2, trans2_segments),  # sub block
            (d1, trans3_segments),  # something 部分（tail_text_segments）
        ]

        result = submit(root, SubmitKind.REPLACE, mappings)
        result_str = element_to_string(result)

        expected = """
            <div>
                <div id="d1">你好世界<span>子块</span>某些东西</div>
            </div>
        """
        self.assertEqual(normalize_whitespace(result_str).strip(), normalize_whitespace(expected).strip())


class TestSubmitAppendText(unittest.TestCase):
    """测试 APPEND_TEXT 模式"""

    def test_append_text_simple(self):
        """测试 APPEND_TEXT 模式 - 简单追加"""
        xml_str = """
        <div>
            <p id="p1">hello world</p>
        </div>
        """
        root = parse_xml(xml_str)
        p1 = find_element_by_id(root, "p1")

        # 构造译文并提取 TextSegments
        translated_xml = parse_xml("<span>你好世界</span>")
        translated_segments = list(search_text_segments(translated_xml))

        mappings: list[InlineSegmentMapping] = [(p1, translated_segments)]

        result = submit(root, SubmitKind.APPEND_TEXT, mappings)
        result_str = element_to_string(result)

        expected = """
            <div>
                <p id="p1">hello world 你好世界</p>
            </div>
        """
        self.assertEqual(normalize_whitespace(result_str).strip(), normalize_whitespace(expected).strip())


class TestSubmitAppendBlock(unittest.TestCase):
    """测试 APPEND_BLOCK 模式"""

    def test_append_block_peak(self):
        """测试 APPEND_BLOCK 模式 - Peak 结构"""
        xml_str = """
        <div>
            <p id="p1">hello world</p>
        </div>
        """
        root = parse_xml(xml_str)
        p1 = find_element_by_id(root, "p1")

        # 构造译文并提取 TextSegments
        translated_xml = parse_xml("<p>你好世界</p>")
        translated_segments = list(search_text_segments(translated_xml))

        mappings: list[InlineSegmentMapping] = [(p1, translated_segments)]

        result = submit(root, SubmitKind.APPEND_BLOCK, mappings)
        result_str = element_to_string(result)

        expected = """
            <div>
                <p id="p1">hello world</p><p>你好世界</p>
            </div>
        """
        self.assertEqual(normalize_whitespace(result_str).strip(), normalize_whitespace(expected).strip())


class TestSubmitEdgeCases(unittest.TestCase):
    """测试边界情况"""

    def test_empty_mappings(self):
        """测试空 mappings"""
        xml_str = "<div><p>hello</p></div>"
        root = parse_xml(xml_str)

        result = submit(root, SubmitKind.REPLACE, [])

        # 验证：返回原始元素
        self.assertEqual(element_to_string(result), element_to_string(root))

    def test_multiple_non_inline_tags_order(self):
        """测试多个非 inline 标签保持顺序"""
        xml_str = """
        <div>
            <div id="d1">
                hello
                <image src="1.png" id="img1" />
                world
                <image src="2.png" id="img2" />
            </div>
        </div>
        """
        root = parse_xml(xml_str)
        d1 = find_element_by_id(root, "d1")

        # 构造译文：将两部分文本合并翻译
        translated_xml = parse_xml("<div>你好<br />世界</div>")
        translated_segments = list(search_text_segments(translated_xml))

        mappings: list[InlineSegmentMapping] = [(d1, translated_segments)]

        result = submit(root, SubmitKind.REPLACE, mappings)
        result_str = element_to_string(result)

        expected = """
            <div>
                <div>你好世界</div><image src="1.png" id="img1"></image><image src="2.png" id="img2"></image>
            </div>
        """
        self.assertEqual(normalize_whitespace(result_str).strip(), normalize_whitespace(expected).strip())

    def test_tail_text_position_in_append_block(self):
        """测试 APPEND_BLOCK 模式下 tail text 的正确位置"""
        # 简化的测试：验证 tail text 的译文不会出现在父元素的开头
        xml_str = """
        <body>
            <description id="desc">Description text</description>
            Tail text after description.
            <p id="p1">Paragraph text</p>
        </body>
        """
        root = parse_xml(xml_str)
        desc = find_element_by_id(root, "desc")
        p1 = find_element_by_id(root, "p1")

        # 构造译文
        trans1_xml = parse_xml("<description>描述文本</description>")
        trans1_segments = list(search_text_segments(trans1_xml))

        # 简化：只翻译 paragraph
        trans2_xml = parse_xml("<p>段落文本</p>")
        trans2_segments = list(search_text_segments(trans2_xml))

        mappings: list[InlineSegmentMapping] = [
            (desc, trans1_segments),
            (p1, trans2_segments),
        ]

        result = submit(root, SubmitKind.APPEND_BLOCK, mappings)
        result_str = element_to_string(result)

        # 核心验证：确保译文结构正确，tail text 仍在原位置
        # 译文应该按顺序出现：<description> 原文、<description> 译文、tail text、<p> 原文、<p> 译文
        self.assertIn('<description id="desc">Description text</description>', result_str)
        self.assertIn("<description>描述文本</description>", result_str)
        self.assertIn("Tail text after description.", result_str)
        self.assertIn('<p id="p1">Paragraph text</p>', result_str)
        self.assertIn("<p>段落文本</p>", result_str)

        # 验证顺序：description 译文在 tail text 之前
        desc_trans_pos = result_str.find("<description>描述文本</description>")
        tail_text_pos = result_str.find("Tail text after description.")
        p_orig_pos = result_str.find('<p id="p1">Paragraph text</p>')

        self.assertLess(desc_trans_pos, tail_text_pos, "描述译文应在 tail text 之前")
        self.assertLess(tail_text_pos, p_orig_pos, "tail text 应在段落原文之前")


if __name__ == "__main__":
    unittest.main()
