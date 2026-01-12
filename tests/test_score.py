import unittest
from typing import cast
from xml.etree.ElementTree import Element, SubElement

from tiktoken import Encoding

from epub_translator.segment import search_inline_segments, search_text_segments
from epub_translator.xml_translator.score import ScoreSegment, expand_to_score_segments, truncate_score_segment


class MockEncoding:
    """
    Mock Encoding，按字符分割中文，按空格分割英文。
    这样可以精确控制 token 的数量，避免和真实的 tiktoken 耦合。
    """

    def encode(self, text: str) -> list[int]:
        tokens: list[str] = []
        i = 0
        while i < len(text):
            # 处理 XML 标签
            if text[i] == "<":
                end = text.find(">", i)
                if end != -1:
                    tokens.append(text[i : end + 1])
                    i = end + 1
                    continue

            # 处理中文字符
            if "\u4e00" <= text[i] <= "\u9fff":
                tokens.append(text[i])
                i += 1
                continue

            # 处理英文单词
            if text[i].isalpha() and ord(text[i]) < 128:  # 只处理 ASCII 字母
                start = i
                while i < len(text) and text[i].isalpha() and ord(text[i]) < 128:
                    i += 1
                tokens.append(text[start:i])
                continue

            # 处理空格和其他字符
            tokens.append(text[i])
            i += 1

        return cast(list[int], tokens)

    def decode(self, tokens: list[int]) -> str:
        return "".join(cast(list[str], tokens))


# pylint: disable=W0212
class TestTruncateScoreSegment(unittest.TestCase):
    """测试 truncate_score_segment 的截断逻辑"""

    def setUp(self):
        """初始化测试环境"""
        self.encoding: Encoding = cast(Encoding, MockEncoding())

    def _create_score_segment(self, root: Element) -> ScoreSegment:
        """从 Element 创建 ScoreSegment"""
        text_segments = list(search_text_segments(root))
        inline_segments = list(search_inline_segments(text_segments))
        self.assertEqual(len(inline_segments), 1, "测试用例应该只有一个 inline segment")
        inline_segment = inline_segments[0]

        score_segments = list(expand_to_score_segments(self.encoding, inline_segment))
        self.assertEqual(len(score_segments), 1, "测试用例应该只有一个 score segment")
        return score_segments[0]

    def test_truncate_head_chinese_text(self):
        """测试从头部截断中文文本"""
        root = Element("div")
        root.text = "你好世界"

        score_segment = self._create_score_segment(root)

        # score_segment.score 包含：XML 标签 tokens + 文本 tokens
        # 我们保留 XML 标签 + 2 个中文字符（你好）
        xml_overhead = score_segment.score - len(score_segment.text_tokens)
        remain_score = xml_overhead + 2  # "你" + "好"

        result = truncate_score_segment(
            encoding=self.encoding,
            score_segment=score_segment,
            remain_head=True,
            remain_score=remain_score,
        )

        # 验证结果
        self.assertIsNotNone(result)
        assert result is not None
        self.assertNotIn("<", result.text_segment.text)
        self.assertNotIn(">", result.text_segment.text)
        self.assertIn("...", result.text_segment.text)
        self.assertEqual(result.text_segment.text, "你好 ...")

    def test_truncate_tail_chinese_text(self):
        """测试从尾部截断中文文本"""
        root = Element("div")
        root.text = "你好世界"

        score_segment = self._create_score_segment(root)

        # 从尾部保留 2 个中文字符（世界）
        xml_overhead = score_segment.score - len(score_segment.text_tokens)
        remain_score = xml_overhead + 2  # "世" + "界"

        result = truncate_score_segment(
            encoding=self.encoding,
            score_segment=score_segment,
            remain_head=False,
            remain_score=remain_score,
        )

        # 验证结果
        self.assertIsNotNone(result)
        assert result is not None
        self.assertNotIn("<", result.text_segment.text)
        self.assertNotIn(">", result.text_segment.text)
        self.assertIn("...", result.text_segment.text)
        self.assertEqual(result.text_segment.text, "... 世界")

    def test_truncate_head_english_text(self):
        """测试从头部截断英文文本"""
        root = Element("p")
        root.text = "Hello World Test"

        score_segment = self._create_score_segment(root)

        # 保留 "Hello" + " " + "World" (3 个 tokens)
        xml_overhead = score_segment.score - len(score_segment.text_tokens)
        remain_score = xml_overhead + 3

        result = truncate_score_segment(
            encoding=self.encoding,
            score_segment=score_segment,
            remain_head=True,
            remain_score=remain_score,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertNotIn("<", result.text_segment.text)
        self.assertNotIn(">", result.text_segment.text)
        self.assertIn("...", result.text_segment.text)
        self.assertEqual(result.text_segment.text, "Hello World ...")

    def test_truncate_mixed_language(self):
        """测试混合中英文的截断"""
        root = Element("div")
        root.text = "Hello你好World"

        score_segment = self._create_score_segment(root)

        # 保留 "Hello" + "你" + "好" (3 个 tokens)
        xml_overhead = score_segment.score - len(score_segment.text_tokens)
        remain_score = xml_overhead + 3

        result = truncate_score_segment(
            encoding=self.encoding,
            score_segment=score_segment,
            remain_head=True,
            remain_score=remain_score,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertNotIn("<", result.text_segment.text)
        self.assertNotIn(">", result.text_segment.text)
        self.assertIn("...", result.text_segment.text)
        self.assertEqual(result.text_segment.text, "Hello你好 ...")

    def test_truncate_only_tags_returns_none(self):
        """测试当 remain_score 只够包含 XML 开销时，返回 None"""
        root = Element("div")
        root.text = "你好世界"

        score_segment = self._create_score_segment(root)

        # 只保留 XML 开销，不包含任何文本
        xml_overhead = score_segment.score - len(score_segment.text_tokens)
        remain_score = xml_overhead

        result = truncate_score_segment(
            encoding=self.encoding,
            score_segment=score_segment,
            remain_head=True,
            remain_score=remain_score,
        )

        # 应该返回 None
        self.assertIsNone(result)

    def test_truncate_full_segment_returns_full_text(self):
        """测试当 remain_score 足够包含完整内容时，保留完整文本"""
        root = Element("div")
        root.text = "你好"

        score_segment = self._create_score_segment(root)

        # remain_score 足够大，包含所有内容
        remain_score = score_segment.score

        result = truncate_score_segment(
            encoding=self.encoding,
            score_segment=score_segment,
            remain_head=True,
            remain_score=remain_score,
        )

        # 应该返回包含完整文本的 segment（加上省略号）
        self.assertIsNotNone(result)
        assert result is not None
        # 注意：truncate_score_segment 总是会添加省略号
        self.assertIn("...", result.text_segment.text)
        self.assertEqual(result.text_segment.text, "你好 ...")

    def test_truncate_nested_element(self):
        """测试嵌套元素的截断"""
        root = Element("div")
        p = SubElement(root, "p")
        p.text = "这是一段很长的中文文本"

        score_segment = self._create_score_segment(root)

        # 保留部分文本（3 个字）
        xml_overhead = score_segment.score - len(score_segment.text_tokens)
        remain_score = xml_overhead + 3

        result = truncate_score_segment(
            encoding=self.encoding,
            score_segment=score_segment,
            remain_head=True,
            remain_score=remain_score,
        )

        self.assertIsNotNone(result)
        assert result is not None
        # 应该不包含任何 XML 标签
        self.assertNotIn("<", result.text_segment.text)
        self.assertNotIn(">", result.text_segment.text)

    def test_truncate_preserves_text_only(self):
        """测试截断后只保留纯文本，不保留 XML 标签"""
        root = Element("span")
        root.text = "ABCDEFGHIJ"

        score_segment = self._create_score_segment(root)

        # 保留部分文本
        xml_overhead = score_segment.score - len(score_segment.text_tokens)
        remain_score = xml_overhead + 3  # "ABC"

        result = truncate_score_segment(
            encoding=self.encoding,
            score_segment=score_segment,
            remain_head=True,
            remain_score=remain_score,
        )

        self.assertIsNotNone(result)
        assert result is not None
        # 核心验证：不应该包含 XML 标签
        self.assertNotIn("<span", result.text_segment.text)
        self.assertNotIn("id=", result.text_segment.text)
        self.assertNotIn("data-orig-len=", result.text_segment.text)
        self.assertNotIn("</span>", result.text_segment.text)

    def test_truncate_tail_only_tags_returns_none(self):
        """测试从尾部截断，当只包含 XML 开销时返回 None"""
        root = Element("div")
        root.text = "你好世界"

        score_segment = self._create_score_segment(root)

        # 从尾部只保留 XML 开销
        xml_overhead = score_segment.score - len(score_segment.text_tokens)
        remain_score = xml_overhead

        result = truncate_score_segment(
            encoding=self.encoding,
            score_segment=score_segment,
            remain_head=False,
            remain_score=remain_score,
        )

        # 应该返回 None
        self.assertIsNone(result)

    def test_truncate_minimal_text(self):
        """测试截断到最小文本的场景"""
        # 构造一个文本，从尾部截断到最小单位
        root = Element("div")
        root.text = "A B"  # tokens: ["A", " ", "B"]

        score_segment = self._create_score_segment(root)

        # 从尾部保留 1 个 token ("B")
        xml_overhead = score_segment.score - len(score_segment.text_tokens)
        remain_score = xml_overhead + 1

        result = truncate_score_segment(
            encoding=self.encoding,
            score_segment=score_segment,
            remain_head=False,
            remain_score=remain_score,
        )

        # 从尾部保留 1 个 token 是 "B"
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.text_segment.text, "... B")

    def test_truncate_exact_boundary(self):
        """测试精确边界情况：刚好在文本结束处截断"""
        root = Element("div")
        root.text = "ABC"

        score_segment = self._create_score_segment(root)

        # 保留完整的 "ABC"
        xml_overhead = score_segment.score - len(score_segment.text_tokens)
        remain_score = xml_overhead + 1  # "ABC" 是一个 token

        result = truncate_score_segment(
            encoding=self.encoding,
            score_segment=score_segment,
            remain_head=True,
            remain_score=remain_score,
        )

        # 应该包含完整文本
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.text_segment.text, "ABC ...")

    def test_mock_encoding_behavior(self):
        """测试 MockEncoding 的行为是否符合预期"""
        # 测试 XML 标签编码
        tokens = self.encoding.encode('<div id="99">你好</div>')
        self.assertEqual(tokens, ['<div id="99">', "你", "好", "</div>"])

        # 测试英文编码
        tokens = self.encoding.encode("Hello World")
        self.assertEqual(tokens, ["Hello", " ", "World"])

        # 测试混合编码
        tokens = self.encoding.encode("Hello你好")
        self.assertEqual(tokens, ["Hello", "你", "好"])

        # 测试解码
        decoded = self.encoding.decode(cast(list[int], ["Hello", " ", "你", "好"]))
        self.assertEqual(decoded, "Hello 你好")


if __name__ == "__main__":
    unittest.main()
