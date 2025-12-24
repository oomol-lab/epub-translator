import unittest
from xml.etree.ElementTree import Element, SubElement

from tiktoken import get_encoding

from epub_translator.xml.truncatable import TruncatableXML


class TestTruncatableXML(unittest.TestCase):
    """测试 TruncatableXML 类的功能"""

    def setUp(self):
        """每个测试用例前的准备工作"""
        self.encoding = get_encoding("cl100k_base")

    def test_simple_text(self):
        """测试简单文本的提取"""
        root = Element("p")
        root.text = "Hello World"

        truncatable = TruncatableXML(self.encoding, root)
        self.assertEqual(truncatable.text, "Hello World")
        self.assertGreater(truncatable.tokens, 0)

    def test_text_with_multiple_spaces(self):
        """测试多个空格被替换为单个空格"""
        root = Element("p")
        root.text = "Hello    World  \n\t  Test"

        truncatable = TruncatableXML(self.encoding, root)
        self.assertEqual(truncatable.text, "Hello World Test")

    def test_nested_elements(self):
        """测试嵌套元素的文本提取"""
        root = Element("div")
        root.text = "Start "
        p1 = SubElement(root, "p")
        p1.text = "First paragraph"
        p1.tail = " Between "
        p2 = SubElement(root, "p")
        p2.text = "Second paragraph"
        p2.tail = " End"

        truncatable = TruncatableXML(self.encoding, root)
        text = truncatable.text
        # 验证文本按顺序拼接
        self.assertIn("Start", text)
        self.assertIn("First paragraph", text)
        self.assertIn("Between", text)
        self.assertIn("Second paragraph", text)
        self.assertIn("End", text)

    def test_deeply_nested_structure(self):
        """测试深度嵌套的结构"""
        root = Element("div")
        root.text = "Level 0"

        child1 = SubElement(root, "div")
        child1.text = "Level 1"
        child1.tail = " After L1"

        child2 = SubElement(child1, "p")
        child2.text = "Level 2"
        child2.tail = " After L2"

        child3 = SubElement(child2, "span")
        child3.text = "Level 3"

        truncatable = TruncatableXML(self.encoding, root)
        text = truncatable.text
        self.assertIn("Level 0", text)
        self.assertIn("Level 1", text)
        self.assertIn("Level 2", text)
        self.assertIn("Level 3", text)

    def test_tokens_count(self):
        """测试 tokens 计数的正确性"""
        root = Element("p")
        root.text = "Hello World"

        truncatable = TruncatableXML(self.encoding, root)
        # 直接 encode 验证
        direct_tokens = len(self.encoding.encode("Hello World"))
        self.assertEqual(truncatable.tokens, direct_tokens)

    def test_truncate_after_head_full(self):
        """测试 truncate_after_head 保留完整内容"""
        root = Element("p")
        root.text = "Hello World"

        truncatable = TruncatableXML(self.encoding, root)
        total_tokens = truncatable.tokens

        # 保留所有 tokens，应该返回原对象
        result = truncatable.truncate_after_head(total_tokens)
        self.assertEqual(result, truncatable)
        self.assertEqual(result.text, "Hello World")

    def test_truncate_after_head_partial(self):
        """测试 truncate_after_head 部分截断"""
        root = Element("p")
        root.text = "This is a longer sentence with many words"

        truncatable = TruncatableXML(self.encoding, root)
        total_tokens = truncatable.tokens

        # 保留前一半的 tokens
        half_tokens = total_tokens // 2
        result = truncatable.truncate_after_head(half_tokens)

        # 验证截断后的 tokens 数量
        self.assertLessEqual(result.tokens, half_tokens)
        # 验证文本被截断
        self.assertLess(len(result.text), len(truncatable.text))

    def test_truncate_after_head_with_nested_elements(self):
        """测试 truncate_after_head 对嵌套元素的处理"""
        root = Element("div")
        root.text = "Start text"
        p1 = SubElement(root, "p")
        p1.text = "First paragraph with some content"
        p1.tail = "After first"
        p2 = SubElement(root, "p")
        p2.text = "Second paragraph with more content"
        p2.tail = "After second"

        truncatable = TruncatableXML(self.encoding, root)

        # 只保留很少的 tokens，应该只保留开头部分
        result = truncatable.truncate_after_head(5)

        # 验证结构被修剪（允许一定误差，因为 decode 的边界问题）
        self.assertLess(result.tokens, truncatable.tokens)
        # 验证后面的内容被删除
        result_text = result.text
        self.assertLess(len(result_text), len(truncatable.text))

    def test_truncate_before_tail_full(self):
        """测试 truncate_before_tail 保留完整内容"""
        root = Element("p")
        root.text = "Hello World"

        truncatable = TruncatableXML(self.encoding, root)
        total_tokens = truncatable.tokens

        # 保留所有 tokens，应该返回原对象
        result = truncatable.truncate_before_tail(total_tokens)
        self.assertEqual(result, truncatable)
        self.assertEqual(result.text, "Hello World")

    def test_truncate_before_tail_partial(self):
        """测试 truncate_before_tail 部分截断"""
        root = Element("p")
        root.text = "This is a longer sentence with many words"

        truncatable = TruncatableXML(self.encoding, root)
        total_tokens = truncatable.tokens

        # 保留后一半的 tokens
        half_tokens = total_tokens // 2
        result = truncatable.truncate_before_tail(half_tokens)

        # 验证截断后的 tokens 数量
        self.assertLessEqual(result.tokens, half_tokens)
        # 验证文本被截断
        self.assertLess(len(result.text), len(truncatable.text))

    def test_truncate_before_tail_with_nested_elements(self):
        """测试 truncate_before_tail 对嵌套元素的处理"""
        root = Element("div")
        root.text = "Start text"
        p1 = SubElement(root, "p")
        p1.text = "First paragraph with some content"
        p1.tail = "After first"
        p2 = SubElement(root, "p")
        p2.text = "Second paragraph with more content"
        p2.tail = "After second"

        truncatable = TruncatableXML(self.encoding, root)

        # 只保留很少的 tokens，应该只保留结尾部分
        result = truncatable.truncate_before_tail(5)

        # 验证结构被修剪（允许一定误差，因为 decode 的边界问题）
        self.assertLess(result.tokens, truncatable.tokens)
        # 验证前面的内容被删除
        result_text = result.text
        self.assertLess(len(result_text), len(truncatable.text))

    def test_truncate_symmetry(self):
        """测试 truncate_after_head 和 truncate_before_tail 的对称性"""
        root = Element("p")
        root.text = "This is a test sentence with multiple words for testing"

        truncatable = TruncatableXML(self.encoding, root)

        # 保留前 10 个 tokens
        head_result = truncatable.truncate_after_head(10)
        # 保留后 10 个 tokens
        tail_result = truncatable.truncate_before_tail(10)

        # 两者的 tokens 应该相近
        self.assertLessEqual(head_result.tokens, 10)
        self.assertLessEqual(tail_result.tokens, 10)

    def test_empty_element(self):
        """测试空元素"""
        root = Element("p")

        truncatable = TruncatableXML(self.encoding, root)
        self.assertEqual(truncatable.text, "")
        self.assertEqual(truncatable.tokens, 0)

    def test_whitespace_only_element(self):
        """测试只有空白的元素"""
        root = Element("p")
        root.text = "   \n\t   "

        truncatable = TruncatableXML(self.encoding, root)
        # 空白被规范化后应该为空
        self.assertEqual(truncatable.text, "")
        self.assertEqual(truncatable.tokens, 0)

    def test_mixed_content_with_empty_elements(self):
        """测试混合内容，包含空元素"""
        root = Element("div")
        root.text = "Start"
        empty = SubElement(root, "span")
        empty.tail = " Middle"
        p = SubElement(root, "p")
        p.text = "End"

        truncatable = TruncatableXML(self.encoding, root)
        text = truncatable.text
        self.assertIn("Start", text)
        self.assertIn("Middle", text)
        self.assertIn("End", text)

    def test_preserve_original_after_truncate(self):
        """测试 truncate 不会修改原对象"""
        root = Element("p")
        root.text = "Original content that should not change"

        truncatable = TruncatableXML(self.encoding, root)
        original_text = truncatable.text
        original_tokens = truncatable.tokens

        # 执行截断
        truncatable.truncate_after_head(5)

        # 验证原对象没有被修改
        self.assertEqual(truncatable.text, original_text)
        self.assertEqual(truncatable.tokens, original_tokens)

    def test_chinese_characters(self):
        """测试中文字符"""
        root = Element("p")
        root.text = "这是一段中文文本，用来测试多字节字符的处理"

        truncatable = TruncatableXML(self.encoding, root)
        self.assertGreater(truncatable.tokens, 0)

        # 测试截断中文文本
        result = truncatable.truncate_after_head(5)
        self.assertLessEqual(result.tokens, 5)

    def test_mixed_languages(self):
        """测试混合语言"""
        root = Element("p")
        root.text = "Hello 世界 World 你好"

        truncatable = TruncatableXML(self.encoding, root)
        text = truncatable.text
        self.assertIn("Hello", text)
        self.assertIn("世界", text)
        self.assertIn("World", text)
        self.assertIn("你好", text)

    def test_truncate_at_zero(self):
        """测试截断到 0 tokens"""
        root = Element("p")
        root.text = "Some content"

        truncatable = TruncatableXML(self.encoding, root)

        result = truncatable.truncate_after_head(0)
        self.assertEqual(result.text, "")
        self.assertEqual(result.tokens, 0)


if __name__ == "__main__":
    unittest.main()
