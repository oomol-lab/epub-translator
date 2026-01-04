import unittest
from xml.etree.ElementTree import Element, SubElement, fromstring, tostring

from epub_translator.segment.text_segment import combine_text_segments, search_text_segments


class TestSearchTextSegments(unittest.TestCase):
    """测试 search_text_segments 文本片段提取功能"""

    def test_search_simple_text(self):
        """测试提取简单文本"""
        root = Element("p")
        root.text = "Hello World"

        segments = list(search_text_segments(root))

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].text, "Hello World")

    def test_search_nested_element(self):
        """测试提取嵌套元素中的文本"""
        root = Element("p")
        em = SubElement(root, "em")
        em.text = "emphasized"

        segments = list(search_text_segments(root))

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].text, "emphasized")

    def test_search_text_and_tail(self):
        """测试提取 TEXT 和 TAIL 文本"""
        root = Element("p")
        root.text = "Before"
        em = SubElement(root, "em")
        em.text = "middle"
        em.tail = "After"

        segments = list(search_text_segments(root))

        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0].text, "Before")
        self.assertEqual(segments[1].text, "middle")
        self.assertEqual(segments[2].text, "After")

    def test_search_multiple_siblings(self):
        """测试提取兄弟元素"""
        root = Element("div")
        p1 = SubElement(root, "p")
        p1.text = "Paragraph 1"
        p2 = SubElement(root, "p")
        p2.text = "Paragraph 2"

        segments = list(search_text_segments(root))

        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].text, "Paragraph 1")
        self.assertEqual(segments[1].text, "Paragraph 2")

    def test_search_ignores_empty_text(self):
        """测试忽略空白文本"""
        root = Element("p")
        root.text = "   "  # 纯空白
        span = SubElement(root, "span")
        span.text = "Content"
        span.tail = "\n\t"  # 纯空白

        segments = list(search_text_segments(root))

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].text, "Content")

    def test_search_normalizes_whitespace(self):
        """测试规范化空白字符"""
        root = Element("p")
        root.text = "Hello  \n\t  World"

        segments = list(search_text_segments(root))

        self.assertEqual(len(segments), 1)
        # 空白字符应该被规范化
        self.assertIn("Hello", segments[0].text)
        self.assertIn("World", segments[0].text)

    def test_search_complex_nesting(self):
        """测试复杂嵌套结构"""
        # <div><p>A<span>B<em>C</em>D</span>E</p>F</div>
        root = fromstring("<div><p>A<span>B<em>C</em>D</span>E</p>F</div>")

        segments = list(search_text_segments(root))

        self.assertEqual(len(segments), 6)
        texts = [seg.text for seg in segments]
        self.assertEqual(texts, ["A", "B", "C", "D", "E", "F"])


class TestCombineTextSegments(unittest.TestCase):
    """测试 combine_text_segments 文本片段组合功能"""

    def test_combine_simple_text(self):
        """测试组合简单文本"""
        root = Element("p")
        root.text = "Hello"

        segments = list(search_text_segments(root))
        rebuilt = list(e for e, _ in combine_text_segments(segments))

        self.assertEqual(len(rebuilt), 1)
        self.assertEqual(rebuilt[0].tag, "p")
        self.assertEqual(rebuilt[0].text, "Hello")

    def test_combine_with_nested_element(self):
        """测试组合嵌套元素"""
        root = Element("p")
        em = SubElement(root, "em")
        em.text = "emphasized"

        segments = list(search_text_segments(root))
        rebuilt = list(e for e, _ in combine_text_segments(segments))

        self.assertEqual(len(rebuilt), 1)
        self.assertEqual(rebuilt[0].tag, "p")
        children = list(rebuilt[0])
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].tag, "em")
        self.assertEqual(children[0].text, "emphasized")

    def test_combine_preserves_attributes(self):
        """测试保留元素属性"""
        root = Element("p")
        root.set("class", "text")
        root.set("id", "p1")
        root.text = "Content"

        segments = list(search_text_segments(root))
        rebuilt = list(e for e, _ in combine_text_segments(segments))

        self.assertEqual(rebuilt[0].get("class"), "text")
        self.assertEqual(rebuilt[0].get("id"), "p1")
        self.assertEqual(rebuilt[0].text, "Content")

    def test_combine_multiple_trees(self):
        """测试处理多棵独立的树"""
        # 创建两个独立的根元素
        root1 = Element("p")
        root1.text = "Tree 1"
        root2 = Element("div")
        root2.text = "Tree 2"

        segments1 = list(search_text_segments(root1))
        segments2 = list(search_text_segments(root2))

        # 组合来自两棵树的 segments
        combined_segments = segments1 + segments2
        rebuilt = list(e for e, _ in combine_text_segments(combined_segments))

        # 应该生成两个独立的根元素
        self.assertEqual(len(rebuilt), 2)
        self.assertEqual(rebuilt[0].tag, "p")
        self.assertEqual(rebuilt[0].text, "Tree 1")
        self.assertEqual(rebuilt[1].tag, "div")
        self.assertEqual(rebuilt[1].text, "Tree 2")


class TestSymmetry(unittest.TestCase):
    """测试 search_text_segments 和 combine_text_segments 的对称性"""

    def _test_roundtrip(self, xml_str: str):
        """辅助方法：测试 XML 的往返转换"""
        original = fromstring(xml_str)
        original_str = tostring(original, encoding="unicode")

        segments = list(search_text_segments(original))
        rebuilt = list(e for e, _ in combine_text_segments(segments))

        self.assertEqual(len(rebuilt), 1)
        rebuilt_str = tostring(rebuilt[0], encoding="unicode")

        self.assertEqual(original_str, rebuilt_str)

    def test_symmetry_simple_text(self):
        """测试对称性：纯文本"""
        self._test_roundtrip("<p>Hello</p>")

    def test_symmetry_nested_element(self):
        """测试对称性：嵌套元素"""
        self._test_roundtrip("<p><em>Hello</em></p>")

    def test_symmetry_text_with_tail(self):
        """测试对称性：TEXT + 嵌套 + TAIL"""
        self._test_roundtrip("<p>A<em>B</em>C</p>")

    def test_symmetry_sibling_blocks(self):
        """测试对称性：兄弟块级元素"""
        self._test_roundtrip("<div><p>Para 1</p><p>Para 2</p></div>")

    def test_symmetry_sibling_inlines(self):
        """测试对称性：兄弟内联元素"""
        self._test_roundtrip("<p><strong>Bold</strong><em>Italic</em></p>")

    def test_symmetry_complex_nesting(self):
        """测试对称性：多层嵌套"""
        self._test_roundtrip("<div><p>A<span>B<em>C</em>D</span>E</p>F</div>")

    def test_symmetry_with_attributes(self):
        """测试对称性：带属性的元素"""
        self._test_roundtrip('<p class="text" id="p1">Content</p>')

    def test_symmetry_multiple_attributes(self):
        """测试对称性：多个嵌套元素带属性"""
        self._test_roundtrip('<div class="container"><p id="p1">A<span data-type="inline">B</span>C</p></div>')


class TestTrimmedSegments(unittest.TestCase):
    """测试删剪场景下的文本组合"""

    def test_trim_tail_becomes_text(self):
        """测试删除 TEXT 后，TAIL 变成 TEXT（视觉正确性）"""
        # 原始: <div><span>A</span>B</div>
        # 删除 A，只保留 B (TAIL)
        root = fromstring("<div><span>A</span>B</div>")
        segments = list(search_text_segments(root))

        # 只保留 segment 2 (B, TAIL)
        trimmed = [segments[1]]
        rebuilt = list(e for e, _ in combine_text_segments(trimmed))

        self.assertEqual(len(rebuilt), 1)
        self.assertEqual(rebuilt[0].tag, "div")
        self.assertEqual(rebuilt[0].text, "B")
        # B 原本是 span 的 tail，删除 A 后变成 div 的 text
        # 这在视觉上是正确的

    def test_trim_consecutive_tails_merge(self):
        """测试连续的 TAIL 文本合并"""
        # 原始: <div><span>A</span>B<em>C</em>D</div>
        # 只保留 B 和 D (都是 TAIL)
        root = fromstring("<div><span>A</span>B<em>C</em>D</div>")
        segments = list(search_text_segments(root))

        # 保留 segments 1 (B) 和 3 (D)
        trimmed = [segments[1], segments[3]]
        rebuilt = list(e for e, _ in combine_text_segments(trimmed))

        self.assertEqual(len(rebuilt), 1)
        self.assertEqual(rebuilt[0].tag, "div")
        self.assertEqual(rebuilt[0].text, "BD")

    def test_trim_tail_then_text(self):
        """测试 TAIL 后跟 TEXT（跨越层级）"""
        # 原始: <div><span>A</span>B<em>C</em></div>
        # 保留 B (TAIL) 和 C (TEXT)
        root = fromstring("<div><span>A</span>B<em>C</em></div>")
        segments = list(search_text_segments(root))

        # 保留 segments 1 (B, TAIL) 和 2 (C, TEXT)
        trimmed = [segments[1], segments[2]]
        rebuilt = list(e for e, _ in combine_text_segments(trimmed))

        self.assertEqual(len(rebuilt), 1)
        result_str = tostring(rebuilt[0], encoding="unicode")
        self.assertEqual(result_str, "<div>B<em>C</em></div>")

    def test_trim_skip_middle_text(self):
        """测试删除中间的 TEXT segment"""
        # 原始: <div><span>A</span><span>B</span>C</div>
        # 删除 B，保留 A 和 C
        root = fromstring("<div><span>A</span><span>B</span>C</div>")
        segments = list(search_text_segments(root))

        # 保留 segments 0 (A) 和 2 (C)
        trimmed = [segments[0], segments[2]]
        rebuilt = list(e for e, _ in combine_text_segments(trimmed))

        self.assertEqual(len(rebuilt), 1)
        self.assertEqual(rebuilt[0].tag, "div")
        # 应该有一个 span 子元素包含 A
        children = list(rebuilt[0])
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].tag, "span")
        self.assertEqual(children[0].text, "A")
        # C 作为 span 的 tail
        self.assertEqual(children[0].tail, "C")

    def test_trim_keeps_structure(self):
        """测试删剪后仍保持基本结构"""
        # 原始: <div><p>A<span>B</span>C</p>D</div>
        # 只保留 B 和 D
        root = fromstring("<div><p>A<span>B</span>C</p>D</div>")
        segments = list(search_text_segments(root))

        # 保留 segments 1 (B) 和 3 (D)
        trimmed = [segments[1], segments[3]]
        rebuilt = list(e for e, _ in combine_text_segments(trimmed))

        self.assertEqual(len(rebuilt), 1)
        result_str = tostring(rebuilt[0], encoding="unicode")
        # 应该保留嵌套结构
        self.assertIn("<div>", result_str)
        self.assertIn("<p>", result_str)
        self.assertIn("<span>", result_str)
        self.assertIn("B", result_str)
        self.assertIn("D", result_str)


class TestEdgeCases(unittest.TestCase):
    """测试边界情况"""

    def test_empty_root(self):
        """测试空根元素"""
        root = Element("p")

        segments = list(search_text_segments(root))

        self.assertEqual(len(segments), 0)

    def test_combine_empty_segments(self):
        """测试组合空的 segment 列表"""
        rebuilt = list(combine_text_segments([]))

        self.assertEqual(len(rebuilt), 0)

    def test_only_whitespace(self):
        """测试只包含空白字符的元素"""
        root = Element("p")
        root.text = "   \n\t   "

        segments = list(search_text_segments(root))

        # 纯空白应该被忽略
        self.assertEqual(len(segments), 0)

    def test_deep_nesting(self):
        """测试深层嵌套"""
        root = Element("div")
        current = root
        for i in range(5):
            child = SubElement(current, f"level{i}")
            child.text = f"Text{i}"
            current = child

        segments = list(search_text_segments(root))

        self.assertEqual(len(segments), 5)
        for i, seg in enumerate(segments):
            self.assertEqual(seg.text, f"Text{i}")

    def test_chinese_text(self):
        """测试中文文本"""
        root = Element("p")
        root.text = "这是中文文本"
        em = SubElement(root, "em")
        em.text = "强调"
        em.tail = "结束"

        segments = list(search_text_segments(root))
        rebuilt = list(e for e, _ in combine_text_segments(segments))

        self.assertEqual(len(segments), 3)
        result_str = tostring(rebuilt[0], encoding="unicode")
        self.assertIn("这是中文文本", result_str)
        self.assertIn("强调", result_str)
        self.assertIn("结束", result_str)


if __name__ == "__main__":
    unittest.main()
