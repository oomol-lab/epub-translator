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


class TestBugReproduction(unittest.TestCase):
    """测试 Bug 复现 - 复现生产环境的真实 bug"""

    def test_bug_indirect_child_in_platform_structure(self):
        """
        复现生产环境 bug：当 _nest_nodes 将间接子元素（非直接子元素）
        添加到 parent.items 时，_submit_by_text 会因找不到元素而崩溃。

        场景：
        - Parent: <p> 元素，直接子元素是 <span>
        - Child: <math> 元素，实际上是 <span> 的子元素
        - _nest_nodes 通过 _check_includes 发现 <math> 在 <p> 的子树中
        - _nest_nodes 将 <math> 添加到 <p> 的 items 中
        - _submit_by_text 应该能够正确处理这种间接子元素的情况

        期望行为：
        - 应该成功提交，不会崩溃
        - 译文应该正确替换到对应位置
        """
        xml_str = """
        <p id="parent">
            <span id="wrapper">
                <math id="math">formula</math>
            </span>
        </p>
        """
        root = parse_xml(xml_str)
        parent = find_element_by_id(root, "parent")
        math = find_element_by_id(root, "math")

        # 创建 mappings 让 _nest_nodes 认为 math 应该是 parent 的 item
        # parent 先出现，然后 math 出现
        # _nest_nodes 会通过 _check_includes 发现 math 在 parent 的子树中
        trans_parent = list(search_text_segments(parse_xml("<p>父元素</p>")))
        trans_math = list(search_text_segments(parse_xml("<math>数学公式</math>")))

        mappings = [
            (parent, trans_parent),
            (math, trans_math),
        ]

        # 应该成功执行，不崩溃
        result = submit(root, SubmitKind.REPLACE, mappings)

        # 验证结果
        self.assertIsNotNone(result)
        result_str = element_to_string(result)

        # 验证译文被正确插入
        self.assertIn("父元素", result_str, "应该包含父元素的译文")
        self.assertIn("数学公式", result_str, "应该包含 math 元素的译文")

        # 验证原始文本被替换
        self.assertNotIn("formula", result_str, "原始文本应该被替换")

        print(f"\n✓ Test passed! Result:\n{result_str}")

    def test_platform_with_multiple_tail_segments(self):
        """测试 platform 结构，其中 tail_text_segments 被分配给多个子节点"""
        # 这个测试模拟一个场景：父元素有多个子元素，翻译时被拆分
        xml_str = """
        <body>
            <div id="parent">
                Text before.
                <p id="child1">Child 1 content</p>
                Text between (this is tail of child1).
                <p id="child2">Child 2 content</p>
                Text after (this is tail of child2).
            </div>
        </body>
        """
        root = parse_xml(xml_str)
        parent = find_element_by_id(root, "parent")
        child1 = find_element_by_id(root, "child1")
        child2 = find_element_by_id(root, "child2")

        # 模拟一个翻译场景：
        # - parent 的 "Text before." 被翻译
        # - child1 被翻译
        # - parent 的 "Text between" 被翻译（作为 tail_text_segments）
        # - child2 被翻译
        # - parent 的 "Text after" 被翻译（作为 tail_text_segments）

        trans_before = list(search_text_segments(parse_xml("<span>之前的文字。</span>")))
        trans_child1 = list(search_text_segments(parse_xml("<p>子元素1内容</p>")))
        trans_between = list(search_text_segments(parse_xml("<span>之间的文字。</span>")))
        trans_child2 = list(search_text_segments(parse_xml("<p>子元素2内容</p>")))
        trans_after = list(search_text_segments(parse_xml("<span>之后的文字。</span>")))

        # 关键：mappings 的顺序模拟 platform 结构
        # parent 出现多次，因为它有多个 tail_text_segments
        mappings: list[InlineSegmentMapping] = [
            (parent, trans_before),  # parent 的 text
            (child1, trans_child1),  # child1
            (parent, trans_between),  # parent 的第一个 tail_text_segments
            (child2, trans_child2),  # child2
            (parent, trans_after),  # parent 的第二个 tail_text_segments
        ]

        result = submit(root, SubmitKind.REPLACE, mappings)
        print("Platform result:", element_to_string(result))

    def test_platform_with_inline_child_between(self):
        """测试 platform 结构，child2 是 inline tag 且在 child1 之后"""
        # 关键场景：child2 是 inline tag，可能在 _remove_elements_after_tail 中被删除
        xml_str = """
        <body>
            <div id="parent">
                Text before.
                <p id="child1">Block child</p>
                <span id="child2">Inline child</span>
                Text after.
            </div>
        </body>
        """
        root = parse_xml(xml_str)
        parent = find_element_by_id(root, "parent")
        child1 = find_element_by_id(root, "child1")
        child2 = find_element_by_id(root, "child2")

        trans_before = list(search_text_segments(parse_xml("<span>之前</span>")))
        trans_child1 = list(search_text_segments(parse_xml("<p>块元素</p>")))
        trans_between = list(search_text_segments(parse_xml("<span>之间</span>")))
        trans_child2 = list(search_text_segments(parse_xml("<span>内联元素</span>")))
        trans_after = list(search_text_segments(parse_xml("<span>之后</span>")))

        mappings: list[InlineSegmentMapping] = [
            (parent, trans_before),
            (child1, trans_child1),
            (parent, trans_between),  # 这将触发第二次处理，此时 child2 可能已被删除
            (child2, trans_child2),
            (parent, trans_after),
        ]

        result = submit(root, SubmitKind.REPLACE, mappings)
        print("Inline child result:", element_to_string(result))


if __name__ == "__main__":
    unittest.main()
