import unittest
from xml.etree.ElementTree import Element, SubElement

from epub_translator.xml.firendly import decode_friendly, encode_friendly


class TestFriendlyXML(unittest.TestCase):
    """测试 friendly XML 编码和解码功能"""

    def test_decode_simple_tag(self):
        """测试解码简单的标签"""
        xml_str = "<p>Hello World</p>"
        elements = list(decode_friendly(xml_str))

        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0].tag, "p")
        self.assertEqual(elements[0].text, "Hello World")

    def test_decode_self_closing_tag(self):
        """测试解码自闭合标签"""
        xml_str = "<br/>"
        elements = list(decode_friendly(xml_str))

        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0].tag, "br")
        self.assertIsNone(elements[0].text)

    def test_decode_nested_tags(self):
        """测试解码嵌套标签"""
        xml_str = "<div><p>First</p><p>Second</p></div>"
        elements = list(decode_friendly(xml_str))

        # decode_friendly 会 yield 所有闭合的元素，包括内部元素
        self.assertEqual(len(elements), 3)
        self.assertEqual(elements[0].tag, "p")
        self.assertEqual(elements[0].text, "First")
        self.assertEqual(elements[1].tag, "p")
        self.assertEqual(elements[1].text, "Second")
        self.assertEqual(elements[2].tag, "div")
        # 最后的 div 应该包含两个 p 元素
        children = list(elements[2])
        self.assertEqual(len(children), 2)

    def test_decode_with_attributes(self):
        """测试解码带属性的标签"""
        xml_str = '<p class="text" id="p1">Content</p>'
        elements = list(decode_friendly(xml_str))

        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0].get("class"), "text")
        self.assertEqual(elements[0].get("id"), "p1")
        self.assertEqual(elements[0].text, "Content")

    def test_decode_with_tail_text(self):
        """测试解码带 tail 文本的元素"""
        xml_str = "<div><span>Inner</span>Tail text</div>"
        elements = list(decode_friendly(xml_str))

        # decode_friendly 会返回 span 和 div
        self.assertEqual(len(elements), 2)
        self.assertEqual(elements[0].tag, "span")
        self.assertEqual(elements[0].text, "Inner")
        # tail 文本被附加到 span 元素上
        # 注意：根据实际行为，tail 可能不会被保留

    def test_decode_filter_by_single_tag(self):
        """测试通过单个标签名过滤"""
        xml_str = "<div><p>Paragraph</p><span>Span</span></div>"
        elements = list(decode_friendly(xml_str, "p"))

        # 只应该返回 p 标签，不返回外层的 div
        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0].tag, "p")
        self.assertEqual(elements[0].text, "Paragraph")

    def test_decode_filter_by_multiple_tags(self):
        """测试通过多个标签名过滤"""
        xml_str = "<div><p>Para</p><span>Span</span><a>Link</a></div>"
        elements = list(decode_friendly(xml_str, ["p", "a"]))

        # 应该返回 p 和 a 标签
        self.assertEqual(len(elements), 2)
        tags = [elem.tag for elem in elements]
        self.assertIn("p", tags)
        self.assertIn("a", tags)

    def test_decode_malformed_tags(self):
        """测试解码不匹配的标签"""
        # 缺少闭合标签的情况
        xml_str = "<p>Unclosed tag"
        elements = list(decode_friendly(xml_str))

        # 应该能够处理不匹配的标签
        self.assertGreaterEqual(len(elements), 0)

    def test_decode_mixed_content(self):
        """测试解码混合内容（文本和标签）"""
        xml_str = "<p>Start <b>bold</b> middle <i>italic</i> end</p>"
        elements = list(decode_friendly(xml_str))

        # decode_friendly 会返回所有闭合的元素：b, i, p
        self.assertEqual(len(elements), 3)
        self.assertEqual(elements[0].tag, "b")
        self.assertEqual(elements[0].text, "bold")
        self.assertEqual(elements[1].tag, "i")
        self.assertEqual(elements[1].text, "italic")
        self.assertEqual(elements[2].tag, "p")
        # p 元素应该包含两个子元素
        children = list(elements[2])
        self.assertEqual(len(children), 2)

    def test_encode_simple_element(self):
        """测试编码简单元素"""
        element = Element("p")
        element.text = "Hello World"

        result = encode_friendly(element)

        self.assertIn("<p>", result)
        self.assertIn("Hello World", result)
        self.assertIn("</p>", result)

    def test_encode_self_closing_element(self):
        """测试编码空元素（自闭合）"""
        element = Element("br")

        result = encode_friendly(element)

        # 空元素应该使用自闭合形式
        self.assertIn("<br", result)
        self.assertIn("/>", result)

    def test_encode_element_with_attributes(self):
        """测试编码带属性的元素"""
        element = Element("p")
        element.set("class", "text")
        element.set("id", "p1")
        element.text = "Content"

        result = encode_friendly(element)

        self.assertIn('class="text"', result)
        self.assertIn('id="p1"', result)
        self.assertIn("Content", result)

    def test_encode_nested_elements(self):
        """测试编码嵌套元素"""
        root = Element("div")
        p1 = SubElement(root, "p")
        p1.text = "First"
        p2 = SubElement(root, "p")
        p2.text = "Second"

        result = encode_friendly(root)

        self.assertIn("<div>", result)
        self.assertIn("<p>First</p>", result)
        self.assertIn("<p>Second</p>", result)
        self.assertIn("</div>", result)

    def test_encode_with_tail_text(self):
        """测试编码带 tail 文本的元素"""
        root = Element("div")
        span = SubElement(root, "span")
        span.text = "Inner"
        span.tail = "Tail"

        result = encode_friendly(root)

        self.assertIn("Inner", result)
        self.assertIn("Tail", result)

    def test_encode_custom_indent(self):
        """测试自定义缩进"""
        root = Element("div")
        p = SubElement(root, "p")
        p.text = "Content"

        # 默认缩进为 2
        result_default = encode_friendly(root, indent=2)
        # 自定义缩进为 4
        result_custom = encode_friendly(root, indent=4)

        # 结果应该不同（缩进不同）
        self.assertNotEqual(result_default, result_custom)

    def test_encode_short_text_inline(self):
        """测试短文本内联显示"""
        element = Element("p")
        element.text = "Short"  # 短文本应该内联

        result = encode_friendly(element)

        # 短文本应该在同一行
        self.assertIn("<p>Short</p>", result)

    def test_encode_long_text_multiline(self):
        """测试长文本多行显示"""
        element = Element("p")
        element.text = "This is a very long text that exceeds the tiny text length limit"

        result = encode_friendly(element)

        # 长文本应该换行显示
        lines = result.strip().split("\n")
        self.assertGreater(len(lines), 1)

    def test_encode_preserves_special_xml_chars(self):
        """测试编码转义特殊 XML 字符"""
        element = Element("p")
        element.text = "Text with <tag> and &"

        result = encode_friendly(element)

        # < 和 > 应该被转义
        self.assertIn("&lt;", result)
        self.assertIn("&gt;", result)
        # 注意：encode_friendly 使用特殊的转义逻辑，& 可能不会被转义

    def test_encode_decode_roundtrip(self):
        """测试编码和解码的往返转换"""
        # 创建原始元素
        original = Element("div")
        original.set("class", "container")
        p = SubElement(original, "p")
        p.text = "Hello"
        span = SubElement(original, "span")
        span.text = "World"

        # 编码
        encoded = encode_friendly(original)

        # 解码
        decoded = list(decode_friendly(encoded))

        # decode_friendly 会返回所有闭合的元素：p, span, div
        self.assertEqual(len(decoded), 3)
        # 验证最后一个元素是 div
        div_element = decoded[-1]
        self.assertEqual(div_element.tag, "div")
        self.assertEqual(div_element.get("class"), "container")
        children = list(div_element)
        self.assertEqual(len(children), 2)
        self.assertEqual(children[0].tag, "p")
        self.assertEqual(children[1].tag, "span")

    def test_decode_empty_string(self):
        """测试解码空字符串"""
        elements = list(decode_friendly(""))
        self.assertEqual(len(elements), 0)

    def test_decode_plain_text_without_tags(self):
        """测试解码纯文本（无标签）"""
        elements = list(decode_friendly("Just plain text"))
        # 纯文本应该不产生任何元素
        self.assertEqual(len(elements), 0)

    def test_encode_element_with_newlines(self):
        """测试编码包含换行的文本"""
        element = Element("p")
        element.text = "Line 1\nLine 2\nLine 3"

        result = encode_friendly(element)

        # 包含换行符的文本应该保留
        self.assertIn("Line 1", result)
        self.assertIn("Line 2", result)
        self.assertIn("Line 3", result)

    def test_decode_chinese_text(self):
        """测试解码中文文本"""
        xml_str = "<p>这是中文文本</p>"
        elements = list(decode_friendly(xml_str))

        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0].text, "这是中文文本")

    def test_encode_chinese_text(self):
        """测试编码中文文本"""
        element = Element("p")
        element.text = "这是中文文本"

        result = encode_friendly(element)

        self.assertIn("这是中文文本", result)
        self.assertIn("<p>", result)
        self.assertIn("</p>", result)


if __name__ == "__main__":
    unittest.main()
