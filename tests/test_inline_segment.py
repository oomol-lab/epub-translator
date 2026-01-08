import unittest
from xml.etree.ElementTree import fromstring, tostring

from epub_translator.segment.inline_segment import (
    InlineSegment,
    InlineUnexpectedIDError,
    InlineWrongTagCountError,
    search_inline_segments,
)
from epub_translator.segment.text_segment import search_text_segments
from epub_translator.xml import ID_KEY, iter_with_stack


def _get_first_inline_segment(segments):
    """辅助函数：从 segments 中获取第一个 InlineSegment"""
    inline_segments = list(search_inline_segments(segments))
    return inline_segments[0] if inline_segments else None


class TestCollectInlineSegment(unittest.TestCase):
    """测试 collect_next_inline_segment 收集内联片段功能"""

    def test_collect_simple_inline(self):
        """测试收集简单的内联元素"""
        # <p>Hello <em>world</em></p>
        root = fromstring("<p>Hello <em>world</em></p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        self.assertIsNotNone(inline_segment)
        assert inline_segment is not None  # for type checker
        # 应该收集两个 text segment
        text_segments = list(inline_segment)
        self.assertEqual(len(text_segments), 2)

    def test_collect_nested_inline(self):
        """测试收集嵌套的内联元素"""
        # <p>A<span>B<em>C</em>D</span>E</p>
        root = fromstring("<p>A<span>B<em>C</em>D</span>E</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        self.assertIsNotNone(inline_segment)
        assert inline_segment is not None  # for type checker
        text_segments = list(inline_segment)
        self.assertEqual(len(text_segments), 5)
        self.assertEqual([s.text for s in text_segments], ["A", "B", "C", "D", "E"])

    def test_collect_separated_same_tags(self):
        """测试收集被文本分隔的相同标签"""
        # <p>X<em>A</em>Y<em>B</em>Z</p>
        root = fromstring("<p>X<em>A</em>Y<em>B</em>Z</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        self.assertIsNotNone(inline_segment)
        assert inline_segment is not None  # for type checker
        # 应该有 5 个 children：X, em, Y, em, Z
        self.assertEqual(len(inline_segment.children), 5)


class TestInlineSegmentIDAssignment(unittest.TestCase):
    """测试 InlineSegment ID 分配逻辑"""

    def test_identical_elements_no_id(self):
        """测试相同属性的元素不分配 ID（全同粒子）"""
        # <p>X<em>A</em>Y<em>B</em>Z</p> - 两个 em 完全相同
        root = fromstring("<p>X<em>A</em>Y<em>B</em>Z</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        # 检查两个 em InlineSegment 的 ID
        em_segments = [c for c in inline_segment.children if isinstance(c, InlineSegment)]
        self.assertEqual(len(em_segments), 2)
        # 相同元素不应该有 ID
        self.assertIsNone(em_segments[0].id)
        self.assertIsNone(em_segments[1].id)

    def test_different_tags_no_id(self):
        """测试不同标签不分配 ID"""
        # <p><strong>A</strong><em>B</em></p> - 不同标签
        root = fromstring("<p><strong>A</strong><em>B</em></p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        inline_children = [c for c in inline_segment.children if isinstance(c, InlineSegment)]
        # 不同标签不需要 ID
        for child in inline_children:
            self.assertIsNone(child.id)


class TestCreateElement(unittest.TestCase):
    """测试 create_element 创建 XML 元素功能"""

    def test_create_simple_element(self):
        """测试创建简单元素"""
        root = fromstring("<p>Hello <em>world</em></p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        element = inline_segment.create_element()

        self.assertEqual(element.tag, "p")
        self.assertTrue("Hello" in (element.text or ""))
        children = list(element)
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].tag, "em")
        self.assertEqual(children[0].text, "world")

    def test_create_element_no_attributes(self):
        """测试 create_element 不复制属性（减少 LLM tokens）"""
        root = fromstring('<p class="text" id="p1">Hello</p>')
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        element = inline_segment.create_element()

        for _, child_element in iter_with_stack(element):
            if id(child_element) == id(element):
                continue
            # 不应该复制属性
            self.assertIsNone(child_element.get("class"))
            self.assertIsNone(child_element.get("id"))

    def test_create_nested_structure(self):
        """测试创建嵌套结构"""
        root = fromstring("<p>A<span>B<em>C</em>D</span>E</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        element = inline_segment.create_element()

        # 验证嵌套结构
        self.assertEqual(element.tag, "p")
        self.assertTrue("A" in (element.text or ""))

        span = element.find(".//span")
        self.assertIsNotNone(span)
        assert span is not None  # for type checker

        em = span.find(".//em")
        self.assertIsNotNone(em)
        assert em is not None  # for type checker
        self.assertEqual(em.text, "C")


class TestValidate(unittest.TestCase):
    """测试 validate 验证功能"""

    def test_validate_correct_structure(self):
        """测试验证正确的结构"""
        root = fromstring("<p>X<em>A</em>Y<em>B</em>Z</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        # 创建相同结构的验证元素
        validated = fromstring("<p>译X<em>译A</em>译Y<em>译B</em>译Z</p>")

        errors = list(inline_segment.validate(validated))
        self.assertEqual(len(errors), 0)

    def test_validate_wrong_tag_count(self):
        """测试验证错误的标签数量"""
        root = fromstring("<p>X<em>A</em>Y<em>B</em>Z</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        # 缺少一个 em
        validated = fromstring("<p>译X<em>译A</em>译YZ</p>")

        errors = list(inline_segment.validate(validated))
        self.assertGreater(len(errors), 0)
        # 应该有 InlineWrongTagCountError
        self.assertTrue(any(isinstance(e, InlineWrongTagCountError) for e in errors))

    def test_validate_unexpected_id(self):
        """测试验证意外的 ID"""
        root = fromstring("<p>X<em>A</em>Y<em>B</em>Z</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        # 添加不应该存在的 ID_KEY
        validated = fromstring(f'<p>译X<em {ID_KEY}="999">译A</em>译Y<em>译B</em>译Z</p>')

        errors = list(inline_segment.validate(validated))
        # 应该有 InlineUnexpectedIDError
        unexpected_errors = [e for e in errors if isinstance(e, InlineUnexpectedIDError)]
        self.assertGreater(len(unexpected_errors), 0)


class TestAssignAttributes(unittest.TestCase):
    """测试 assign_attributes 属性映射功能"""

    def test_assign_preserves_original_attributes(self):
        """测试保留原始元素的属性"""
        root = fromstring('<p class="original">Hello <em>world</em></p>')
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        # 模板元素有不同的属性
        template = fromstring('<p class="translated">你好 <em>世界</em></p>')

        result = inline_segment.assign_attributes(template)

        # 应该保留原始的属性
        self.assertEqual(result.get("class"), "original")
        self.assertEqual(result.tag, "p")


class TestMatchChildren(unittest.TestCase):
    """测试 _match_children 子元素匹配功能"""

    def test_match_by_natural_order(self):
        """测试通过自然顺序匹配（无 ID）"""
        root = fromstring("<p>X<em>A</em>Y<em>B</em>Z</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        # 没有 ID，按顺序匹配
        template = fromstring("<p>译X<em>译A</em>译Y<em>译B</em>译Z</p>")

        # pylint: disable=protected-access
        matches = list(inline_segment._match_children(template))  # type: ignore[attr-defined]

        self.assertEqual(len(matches), 2)


class TestEdgeCases(unittest.TestCase):
    """测试边界情况"""

    def test_empty_inline_segment(self):
        """测试空的内联结构"""
        root = fromstring("<p></p>")
        segments = list(search_text_segments(root))

        # 空元素没有 segments
        self.assertEqual(len(segments), 0)

    def test_single_text_segment(self):
        """测试单个文本片段"""
        root = fromstring("<p>Hello</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        self.assertIsNotNone(inline_segment)
        assert inline_segment is not None  # for type checker
        text_segments = list(inline_segment)
        self.assertEqual(len(text_segments), 1)

    def test_deeply_nested_structure(self):
        """测试深层嵌套结构"""
        root = fromstring("<p><span><em><strong>Deep</strong></em></span></p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        element = inline_segment.create_element()

        # 验证深层嵌套
        strong = element.find(".//strong")
        self.assertIsNotNone(strong)
        assert strong is not None  # for type checker
        self.assertEqual(strong.text, "Deep")

    def test_chinese_text_handling(self):
        """测试中文文本处理"""
        root = fromstring("<p>这是<em>中文</em>文本</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        element = inline_segment.create_element()

        result_str = tostring(element, encoding="unicode")
        self.assertIn("这是", result_str)
        self.assertIn("中文", result_str)
        self.assertIn("文本", result_str)

    def test_multiple_different_tags(self):
        """测试多种不同标签混合 - 相邻的不同标签会被合并"""
        root = fromstring("<p><em>A</em><strong>B</strong><span>C</span></p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        element = inline_segment.create_element()

        # 验证元素被创建
        self.assertGreater(len(list(element)), 0)
        # 验证至少包含一个标签
        result_str = tostring(element, encoding="unicode")
        self.assertIn("<em>", result_str)

    def test_parent_with_text_and_child_blocks_not_merged(self):
        root = fromstring("<body>The main text begins:<p>Paragraph text</p><div>Division text</div></body>")
        segments = list(search_text_segments(root))

        # 应该有 3 个 text segments:
        # 1. "The main text begins:" in body
        # 2. "Paragraph text" in p
        # 3. "Division text" in div
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0].block_parent.tag, "body")
        self.assertEqual(segments[1].block_parent.tag, "p")
        self.assertEqual(segments[2].block_parent.tag, "div")

        # 获取所有 inline segments
        inline_segments = list(search_inline_segments(segments))

        # 应该有 3 个独立的 inline segments
        self.assertEqual(len(inline_segments), 3)

        # 验证第一个 inline segment (body 的文本)
        inline1 = inline_segments[0]
        body_texts = list(inline1)
        self.assertEqual(len(body_texts), 1)
        self.assertEqual(body_texts[0].text, "The main text begins:")
        self.assertEqual(inline1.parent.tag, "body")

        # 验证第二个 inline segment (p 的文本)
        inline2 = inline_segments[1]
        p_texts = list(inline2)
        self.assertEqual(len(p_texts), 1)
        self.assertEqual(p_texts[0].text, "Paragraph text")
        self.assertEqual(inline2.parent.tag, "p")

        # 验证第三个 inline segment (div 的文本)
        inline3 = inline_segments[2]
        div_texts = list(inline3)
        self.assertEqual(len(div_texts), 1)
        self.assertEqual(div_texts[0].text, "Division text")
        self.assertEqual(inline3.parent.tag, "div")


if __name__ == "__main__":
    unittest.main()
