import unittest
from typing import cast
from xml.etree.ElementTree import Element, SubElement

from tiktoken import Encoding

from epub_translator.segment import search_text_segments
from epub_translator.xml_translator.stream_mapper import XMLStreamMapper


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
class TestTruncateTextSegment(unittest.TestCase):
    """测试 XMLStreamMapper._truncate_text_segment 的截断逻辑"""

    def setUp(self):
        """初始化测试环境"""
        self.encoding: Encoding = cast(Encoding, MockEncoding())
        self.mapper = XMLStreamMapper(encoding=self.encoding, max_group_tokens=1000)

    def test_truncate_head_chinese_text(self):
        """测试从头部截断中文文本"""
        # <div id="99" data-orig-len="999">你好世界</div>
        root = Element("div")
        root.text = "你好世界"
        segments = list(search_text_segments(root))
        segment = segments[0]

        raw_xml_text = segment.xml_text
        tokens = self.encoding.encode(raw_xml_text)

        # tokens: ['<div id="99" data-orig-len="999">', '你', '好', '</div>']
        # 保留前 3 个 token: 开标签 + '你' + '好'
        remain_count = 3
        result = self.mapper._truncate_text_segment(
            segment=segment,
            tokens=tokens,
            raw_xml_text=raw_xml_text,
            remain_head=True,
            remain_count=remain_count,
        )

        # 验证结果
        assert result is not None
        self.assertNotIn("<", result.text)
        self.assertNotIn(">", result.text)
        self.assertIn("...", result.text)
        self.assertEqual(result.text, "你好 ...")

    def test_truncate_tail_chinese_text(self):
        """测试从尾部截断中文文本"""
        root = Element("div")
        root.text = "你好世界"
        segments = list(search_text_segments(root))
        segment = segments[0]

        raw_xml_text = segment.xml_text
        tokens = self.encoding.encode(raw_xml_text)

        # tokens: ['<div id="99" data-orig-len="999">', '你', '好', '世', '界', '</div>']
        # 从尾部保留 3 个 token: '世' + '界' + '</div>'
        remain_count = 3
        result = self.mapper._truncate_text_segment(
            segment=segment,
            tokens=tokens,
            raw_xml_text=raw_xml_text,
            remain_head=False,
            remain_count=remain_count,
        )

        # 验证结果
        assert result is not None
        self.assertNotIn("<", result.text)
        self.assertNotIn(">", result.text)
        self.assertIn("...", result.text)
        self.assertEqual(result.text, "... 世界")

    def test_truncate_head_english_text(self):
        """测试从头部截断英文文本"""
        root = Element("p")
        root.text = "Hello World Test"
        segments = list(search_text_segments(root))
        segment = segments[0]

        raw_xml_text = segment.xml_text
        tokens = self.encoding.encode(raw_xml_text)

        # tokens: ['<p id="99" data-orig-len="999">', 'Hello', ' ', 'World', ...]
        # 保留前 4 个 token: 开标签 + 'Hello' + ' ' + 'World'
        remain_count = 4
        result = self.mapper._truncate_text_segment(
            segment=segment,
            tokens=tokens,
            raw_xml_text=raw_xml_text,
            remain_head=True,
            remain_count=remain_count,
        )

        assert result is not None
        self.assertNotIn("<", result.text)
        self.assertNotIn(">", result.text)
        self.assertIn("...", result.text)
        self.assertEqual(result.text, "Hello World ...")

    def test_truncate_mixed_language(self):
        """测试混合中英文的截断"""
        root = Element("div")
        root.text = "Hello你好World"
        segments = list(search_text_segments(root))
        segment = segments[0]

        raw_xml_text = segment.xml_text
        tokens = self.encoding.encode(raw_xml_text)

        # tokens: ['<div id="99" data-orig-len="999">', 'Hello', '你', '好', 'World', '</div>']
        # 保留前 4 个 token: 开标签 + 'Hello' + '你' + '好'
        remain_count = 4
        result = self.mapper._truncate_text_segment(
            segment=segment,
            tokens=tokens,
            raw_xml_text=raw_xml_text,
            remain_head=True,
            remain_count=remain_count,
        )

        self.assertIsNotNone(result)
        assert result is not None  # 类型断言，让 IDE 知道 result 不是 None
        self.assertNotIn("<", result.text)
        self.assertNotIn(">", result.text)
        self.assertIn("...", result.text)
        self.assertEqual(result.text, "Hello你好 ...")

    def test_truncate_only_tags_returns_none(self):
        """测试当 remain_count 只够包含开标签时，返回 None"""
        root = Element("div")
        root.text = "你好世界"
        segments = list(search_text_segments(root))
        segment = segments[0]

        raw_xml_text = segment.xml_text
        tokens = self.encoding.encode(raw_xml_text)

        # 只保留 1 个 token（开标签），不包含任何文本
        remain_count = 1
        result = self.mapper._truncate_text_segment(
            segment=segment,
            tokens=tokens,
            raw_xml_text=raw_xml_text,
            remain_head=True,
            remain_count=remain_count,
        )

        # 应该返回 None
        self.assertIsNone(result)

    def test_truncate_full_segment_returns_original(self):
        """测试当 remain_count 足够包含完整内容时，返回原始 segment"""
        root = Element("div")
        root.text = "你好"
        segments = list(search_text_segments(root))
        segment = segments[0]

        raw_xml_text = segment.xml_text
        tokens = self.encoding.encode(raw_xml_text)

        # remain_count 足够大，包含所有内容
        remain_count = len(tokens)
        result = self.mapper._truncate_text_segment(
            segment=segment,
            tokens=tokens,
            raw_xml_text=raw_xml_text,
            remain_head=True,
            remain_count=remain_count,
        )

        # 应该返回原始 segment，文本不变
        assert result is not None
        self.assertEqual(result.text, "你好")
        self.assertNotIn("...", result.text)

    def test_truncate_nested_element(self):
        """测试嵌套元素的截断"""
        root = Element("div")
        p = SubElement(root, "p")
        p.text = "这是一段很长的中文文本"
        segments = list(search_text_segments(root))
        segment = segments[0]

        raw_xml_text = segment.xml_text
        tokens = self.encoding.encode(raw_xml_text)

        # 保留开标签 + 部分文本
        remain_count = 5  # 两个开标签 + 3 个字
        result = self.mapper._truncate_text_segment(
            segment=segment,
            tokens=tokens,
            raw_xml_text=raw_xml_text,
            remain_head=True,
            remain_count=remain_count,
        )

        assert result is not None
        # 应该不包含任何 XML 标签
        self.assertNotIn("<", result.text)
        self.assertNotIn(">", result.text)

    def test_truncate_preserves_text_only(self):
        """测试截断后只保留纯文本，不保留 XML 标签"""
        root = Element("span")
        root.text = "ABCDEFGHIJ"
        segments = list(search_text_segments(root))
        segment = segments[0]

        raw_xml_text = segment.xml_text
        tokens = self.encoding.encode(raw_xml_text)

        # 保留部分文本
        remain_count = 3  # 开标签 + 'ABCDEFGHIJ' 的前面部分
        result = self.mapper._truncate_text_segment(
            segment=segment,
            tokens=tokens,
            raw_xml_text=raw_xml_text,
            remain_head=True,
            remain_count=remain_count,
        )

        assert result is not None
        # 核心验证：不应该包含 XML 标签
        self.assertNotIn("<span", result.text)
        self.assertNotIn("id=", result.text)
        self.assertNotIn("data-orig-len=", result.text)
        self.assertNotIn("</span>", result.text)

    def test_truncate_tail_only_tags_returns_none(self):
        """测试从尾部截断，当只包含闭标签时返回 None"""
        root = Element("div")
        root.text = "你好世界"
        segments = list(search_text_segments(root))
        segment = segments[0]

        raw_xml_text = segment.xml_text
        tokens = self.encoding.encode(raw_xml_text)

        # 从尾部只保留 1 个 token（闭标签）
        remain_count = 1
        result = self.mapper._truncate_text_segment(
            segment=segment,
            tokens=tokens,
            raw_xml_text=raw_xml_text,
            remain_head=False,
            remain_count=remain_count,
        )

        # 应该返回 None
        self.assertIsNone(result)

    def test_truncate_whitespace_only_returns_none(self):
        """测试当截断后只剩空白字符时返回 None"""
        root = Element("div")
        root.text = "     "  # 只有空白（会被 normalize 成单个空格）
        segments = list(search_text_segments(root))

        # 如果文本只有空白，search_text_segments 会过滤掉
        # 所以这个测试实际上不会产生 segment
        if not segments:
            self.assertEqual(len(segments), 0)
            return

        # 如果产生了 segment（不应该），测试它的行为
        segment = segments[0]
        raw_xml_text = segment.xml_text
        tokens = self.encoding.encode(raw_xml_text)

        # 只保留开标签和空格
        remain_count = 2  # 开标签 + 空格
        result = self.mapper._truncate_text_segment(
            segment=segment,
            tokens=tokens,
            raw_xml_text=raw_xml_text,
            remain_head=True,
            remain_count=remain_count,
        )

        # 如果只剩空白，应该返回 None
        self.assertIsNone(result)

    def test_truncate_exact_boundary(self):
        """测试精确边界情况：刚好在文本开始处截断"""
        root = Element("div")
        root.text = "ABC"
        segments = list(search_text_segments(root))
        segment = segments[0]

        raw_xml_text = segment.xml_text
        tokens = self.encoding.encode(raw_xml_text)

        # tokens: ['<div id="99" data-orig-len="999">', 'ABC', '</div>']
        # 保留前 2 个 token: 开标签 + 'ABC'
        remain_count = 2
        result = self.mapper._truncate_text_segment(
            segment=segment,
            tokens=tokens,
            raw_xml_text=raw_xml_text,
            remain_head=True,
            remain_count=remain_count,
        )

        # 应该包含完整文本
        assert result is not None
        self.assertEqual(result.text, "ABC")
        self.assertNotIn("...", result.text)

    def test_mock_encoding_behavior(self):
        """测试 MockEncoding 的行为是否符合预期"""
        # 测试 XML 标签编码
        tokens = self.encoding.encode('<div id="99" data-orig-len="999">你好</div>')
        self.assertEqual(tokens, ['<div id="99" data-orig-len="999">', "你", "好", "</div>"])

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
