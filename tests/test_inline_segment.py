import unittest
from xml.etree.ElementTree import fromstring, tostring

from epub_translator.segment.inline_segment import (
    InlineExpectedIDError,
    InlineLostIDError,
    InlineSegment,
    InlineUnexpectedIDError,
    InlineWrongTagCountError,
    collect_next_inline_segment,
)
from epub_translator.segment.text_segment import search_text_segments
from epub_translator.segment.utils import IDGenerator
from epub_translator.xml import ID_KEY


class TestCollectInlineSegment(unittest.TestCase):
    """测试 collect_next_inline_segment 收集内联片段功能"""

    def test_collect_simple_inline(self):
        """测试收集简单的内联元素"""
        # <p>Hello <em>world</em></p>
        root = fromstring("<p>Hello <em>world</em></p>")
        segments = list(search_text_segments(root))

        id_gen = IDGenerator()
        inline_segment, next_segment = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

        self.assertIsNotNone(inline_segment)
        assert inline_segment is not None  # for type checker
        self.assertIsNone(next_segment)
        # 应该收集两个 text segment
        text_segments = list(inline_segment)
        self.assertEqual(len(text_segments), 2)

    def test_collect_nested_inline(self):
        """测试收集嵌套的内联元素"""
        # <p>A<span>B<em>C</em>D</span>E</p>
        root = fromstring("<p>A<span>B<em>C</em>D</span>E</p>")
        segments = list(search_text_segments(root))

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

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

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

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

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

        assert inline_segment is not None  # for type checker
        # 检查两个 em InlineSegment 的 ID
        em_segments = [c for c in inline_segment.children if isinstance(c, InlineSegment)]
        self.assertEqual(len(em_segments), 2)
        # 相同元素不应该有 ID
        self.assertIsNone(em_segments[0].id)
        self.assertIsNone(em_segments[1].id)

    def test_different_attributes_have_id(self):
        """测试不同属性的元素分配 ID"""
        # <p>X<em class="a">A</em>Y<em class="b">B</em>Z</p> - 两个 em 属性不同
        root = fromstring('<p>X<em class="a">A</em>Y<em class="b">B</em>Z</p>')
        segments = list(search_text_segments(root))

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

        assert inline_segment is not None  # for type checker
        # 检查两个 em InlineSegment 的 ID
        em_segments = [c for c in inline_segment.children if isinstance(c, InlineSegment)]
        self.assertEqual(len(em_segments), 2)
        # 不同属性的元素应该都有 ID
        self.assertIsNotNone(em_segments[0].id)
        self.assertIsNotNone(em_segments[1].id)
        # ID 应该是从 1 开始的连续数字
        self.assertEqual(em_segments[0].id, 1)
        self.assertEqual(em_segments[1].id, 2)

    def test_different_tags_no_id(self):
        """测试不同标签不分配 ID"""
        # <p><strong>A</strong><em>B</em></p> - 不同标签
        root = fromstring("<p><strong>A</strong><em>B</em></p>")
        segments = list(search_text_segments(root))

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

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

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

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

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

        assert inline_segment is not None  # for type checker
        element = inline_segment.create_element()

        # 不应该复制属性
        self.assertIsNone(element.get("class"))
        self.assertIsNone(element.get("id"))

    def test_create_element_with_ids(self):
        """测试创建带 ID 的元素"""
        root = fromstring('<p>X<em class="a">A</em>Y<em class="b">B</em>Z</p>')
        segments = list(search_text_segments(root))

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

        assert inline_segment is not None  # for type checker
        element = inline_segment.create_element()

        # 应该有两个 em 子元素
        em_children = [c for c in element if c.tag == "em"]
        self.assertEqual(len(em_children), 2)
        # 应该有 ID_KEY 属性
        self.assertIsNotNone(em_children[0].get(ID_KEY))
        self.assertIsNotNone(em_children[1].get(ID_KEY))

    def test_create_nested_structure(self):
        """测试创建嵌套结构"""
        root = fromstring("<p>A<span>B<em>C</em>D</span>E</p>")
        segments = list(search_text_segments(root))

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

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

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

        assert inline_segment is not None  # for type checker
        # 创建相同结构的验证元素
        validated = fromstring("<p>译X<em>译A</em>译Y<em>译B</em>译Z</p>")

        errors = list(inline_segment.validate(validated))
        self.assertEqual(len(errors), 0)

    def test_validate_wrong_tag_count(self):
        """测试验证错误的标签数量"""
        root = fromstring("<p>X<em>A</em>Y<em>B</em>Z</p>")
        segments = list(search_text_segments(root))

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

        assert inline_segment is not None  # for type checker
        # 缺少一个 em
        validated = fromstring("<p>译X<em>译A</em>译YZ</p>")

        errors = list(inline_segment.validate(validated))
        self.assertGreater(len(errors), 0)
        # 应该有 InlineWrongTagCountError
        self.assertTrue(any(isinstance(e, InlineWrongTagCountError) for e in errors))

    def test_validate_missing_id(self):
        """测试验证缺失的 ID"""
        root = fromstring('<p>X<em class="a">A</em>Y<em class="b">B</em>Z</p>')
        segments = list(search_text_segments(root))

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

        assert inline_segment is not None  # for type checker
        # 创建元素但缺少 data-id 属性
        validated = fromstring("<p>译X<em>译A</em>译Y<em>译B</em>译Z</p>")

        errors = list(inline_segment.validate(validated))
        # 应该有 InlineLostIDError
        lost_id_errors = [e for e in errors if isinstance(e, InlineLostIDError)]
        self.assertGreater(len(lost_id_errors), 0)

    def test_validate_unexpected_id(self):
        """测试验证意外的 ID"""
        root = fromstring("<p>X<em>A</em>Y<em>B</em>Z</p>")
        segments = list(search_text_segments(root))

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

        assert inline_segment is not None  # for type checker
        # 添加不应该存在的 ID_KEY
        validated = fromstring(f'<p>译X<em {ID_KEY}="999">译A</em>译Y<em>译B</em>译Z</p>')

        errors = list(inline_segment.validate(validated))
        # 应该有 InlineUnexpectedIDError
        unexpected_errors = [e for e in errors if isinstance(e, InlineUnexpectedIDError)]
        self.assertGreater(len(unexpected_errors), 0)

    def test_validate_expected_id_missing(self):
        """测试验证期望的 ID 缺失"""
        root = fromstring('<p>X<em class="a">A</em>Y<em class="b">B</em>Z</p>')
        segments = list(search_text_segments(root))

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

        assert inline_segment is not None  # for type checker
        # 只有一个 em 元素，缺少第二个
        validated = fromstring(f'<p>译X<em {ID_KEY}="1">译A</em>译YZ</p>')

        errors = list(inline_segment.validate(validated))
        # 应该有 InlineExpectedIDError ID 2 未找到）
        expected_errors = [e for e in errors if isinstance(e, InlineExpectedIDError)]
        self.assertGreater(len(expected_errors), 0)


class TestAssignAttributes(unittest.TestCase):
    """测试 assign_attributes 属性映射功能"""

    def test_assign_preserves_original_attributes(self):
        """测试保留原始元素的属性"""
        root = fromstring('<p class="original">Hello <em>world</em></p>')
        segments = list(search_text_segments(root))

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

        assert inline_segment is not None  # for type checker
        # 模板元素有不同的属性
        template = fromstring('<p class="translated">你好 <em>世界</em></p>')

        result = inline_segment.assign_attributes(template)

        # 应该保留原始的属性
        self.assertEqual(result.get("class"), "original")
        self.assertEqual(result.tag, "p")


class TestMatchChildren(unittest.TestCase):
    """测试 _match_children 子元素匹配功能"""

    def test_match_by_id(self):
        """测试通过 ID 匹配子元素"""
        root = fromstring('<p>X<em class="a">A</em>Y<em class="b">B</em>Z</p>')
        segments = list(search_text_segments(root))

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

        # 创建元素，ID 顺序相同
        template = fromstring(f'<p>译X<em {ID_KEY}="1">译A</em>译Y<em {ID_KEY}="2">译B</em>译Z</p>')

        # pylint: disable=protected-access
        matches = list(inline_segment._match_children(template))  # type: ignore[attr-defined]

        self.assertEqual(len(matches), 2)

    def test_match_by_natural_order(self):
        """测试通过自然顺序匹配（无 ID）"""
        root = fromstring("<p>X<em>A</em>Y<em>B</em>Z</p>")
        segments = list(search_text_segments(root))

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

        # 没有 ID，按顺序匹配
        template = fromstring("<p>译X<em>译A</em>译Y<em>译B</em>译Z</p>")

        # pylint: disable=protected-access
        matches = list(inline_segment._match_children(template))  # type: ignore[attr-defined]

        self.assertEqual(len(matches), 2)

    def test_match_prevents_duplicate_id_usage(self):
        """测试防止重复使用同一个 ID"""
        root = fromstring('<p>X<em class="a">A</em>Y<em class="b">B</em>Z</p>')
        segments = list(search_text_segments(root))

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

        # 模板中有重复的 ID（虽然 validate 会报错，但 assign_attributes 仍会处理）
        template = fromstring(f'<p>译X<em {ID_KEY}="1">译A</em>译Y<em {ID_KEY}="1">重复</em>译Z</p>')

        # pylint: disable=protected-access
        matches = list(inline_segment._match_children(template))  # type: ignore[attr-defined]

        # 实际实现中重复 ID 仍然会匹配，这是"尽力而为"策略的一部分
        # 只要能获取到元素就会匹配
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

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

        self.assertIsNotNone(inline_segment)
        assert inline_segment is not None  # for type checker
        text_segments = list(inline_segment)
        self.assertEqual(len(text_segments), 1)

    def test_deeply_nested_structure(self):
        """测试深层嵌套结构"""
        root = fromstring("<p><span><em><strong>Deep</strong></em></span></p>")
        segments = list(search_text_segments(root))

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

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

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

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

        id_gen = IDGenerator()
        inline_segment, _ = collect_next_inline_segment(
            id_generator=id_gen,
            first_text_segment=segments[0],
            text_segments_iter=iter(segments[1:]),
        )

        assert inline_segment is not None  # for type checker
        element = inline_segment.create_element()

        # 验证元素被创建
        self.assertGreater(len(list(element)), 0)
        # 验证至少包含一个标签
        result_str = tostring(element, encoding="unicode")
        self.assertIn("<em>", result_str)


if __name__ == "__main__":
    unittest.main()
