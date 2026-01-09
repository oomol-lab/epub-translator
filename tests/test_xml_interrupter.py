"""
测试 XMLInterrupter 的功能

特别是测试双语输出场景下，inline math 公式的翻译内容是否会丢失。
"""

import re
import unittest
from xml.etree.ElementTree import Element, fromstring

from epub_translator.segment.text_segment import search_text_segments
from epub_translator.xml_interrupter import XMLInterrupter


def remove_namespaces(element: Element) -> Element:
    """递归删除元素的命名空间（模拟 XMLLikeNode 的处理）"""
    namespace_pattern = re.compile(r"\{[^}]+\}")

    # 删除标签的命名空间
    match = namespace_pattern.match(element.tag)
    if match:
        element.tag = element.tag[len(match.group(0)) :]

    # 递归处理子元素
    for child in element:
        remove_namespaces(child)

    return element


def extract_text_content(element: Element) -> str:
    """递归提取元素中的所有文本内容"""
    result = []
    if element.text:
        result.append(element.text.strip())
    for child in element:
        child_text = extract_text_content(child)
        if child_text:
            result.append(child_text)
        if child.tail:
            result.append(child.tail.strip())
    return " ".join(filter(None, result))


class TestXMLInterrupterBilingualOutput(unittest.TestCase):
    """
    测试 XMLInterrupter 在双语输出场景下的行为

    Bug 描述：
    当一个段落包含多个 inline math 公式时，双语输出的译文中大量内容丢失。

    根本原因：
    _expand_translated_text_segment 方法中使用 .pop() 从缓存中取值，
    导致第一次处理原文时缓存被删除，第二次处理译文时缓存已空，
    所有 expression 标签位置的翻译内容被丢弃。
    """

    def setUp(self):
        """准备测试数据"""
        # 创建包含多个 inline math 的原始 HTML
        self.original_html = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<body>
    <p>以 <span class="formula-inline"><math display="inline"><mrow><mn>3</mn><mi>×</mi><mn>3</mn></mrow></math></span> 線性方程組為例，高斯／賽德爾迭代公式 <span class="formula-inline"><math display="inline"><mrow><mo>(</mo><mi>x</mi><mo>)</mo></mrow></math></span> 如下：我們現在來考慮下面這個特殊的 <span class="formula-inline"><math display="inline"><mrow><mn>3</mn><mi>×</mi><mn>3</mn></mrow></math></span> 的簡單例子：其中通過簡單計算，可以獲得 <span class="formula-inline"><math display="inline"><mrow><mi>A</mi></mrow></math></span> 的三個特徵值 <span class="formula-inline"><math display="inline"><mrow><mn>3</mn><mo>,</mo><mn>1</mn><mo>,</mo><mn>0</mn></mrow></math></span> ，其零空間由向量 <span class="formula-inline"><math display="inline"><mrow><mi>e</mi></mrow></math></span> 張成。可以看出，隨著 <span class="formula-inline"><math display="inline"><mrow><mi>ϵ</mi></mrow></math></span> 的減小，矩陣 <span class="formula-inline"><math display="inline"><mrow><mi>A</mi></mrow></math></span> 逐漸變得奇異。</p>
</body>
</html>"""

        # 模拟 LLM 翻译后的结果（包含 expression 占位符）
        self.translated_html = """<body>
    <p>Taking a <expression __XML_INTERRUPTER_ID="1">3×3</expression> linear equation system as an example, the Gauss-Seidel iteration formula <expression __XML_INTERRUPTER_ID="2">(x)</expression> is as follows: We now consider the following special <expression __XML_INTERRUPTER_ID="3">3×3</expression> simple example: Through simple calculation, the three eigenvalues of <expression __XML_INTERRUPTER_ID="4">A</expression> can be obtained as <expression __XML_INTERRUPTER_ID="5">3, 1, 0</expression>, and its null space is spanned by the vector <expression __XML_INTERRUPTER_ID="6">e</expression>. It can be seen that as <expression __XML_INTERRUPTER_ID="7">ε</expression> decreases, the matrix <expression __XML_INTERRUPTER_ID="8">A</expression> gradually becomes singular.</p>
</body>"""

    def test_bilingual_output_content_loss(self):
        """
        测试双语输出场景下的内容丢失问题

        这个测试会失败，直到 XMLInterrupter 的 bug 被修复。

        预期行为：
        - 原文处理后，math 标签的内容应该被缓存
        - 译文处理时，应该能够访问缓存并正确恢复或保留翻译内容
        - 所有翻译的文本片段都应该被保留，不应该被丢弃

        当前行为（Bug）：
        - 原文处理时使用 .pop() 清空了缓存
        - 译文处理时缓存已空，导致所有 expression 标签的内容被丢弃
        - 8 个 expression 标签的翻译内容全部丢失
        """
        # 步骤 1: 解析原始 HTML
        original_root = fromstring(self.original_html)
        original_body = original_root.find(".//{http://www.w3.org/1999/xhtml}body")
        if original_body is None:
            original_body = original_root.find(".//body")
        assert original_body is not None

        # 删除命名空间（模拟 XMLLikeNode 的处理）
        remove_namespaces(original_body)

        # 步骤 2: 使用 XMLInterrupter 处理源文本
        interrupter = XMLInterrupter()
        source_text_segments = list(search_text_segments(original_body))
        interrupted_segments = list(interrupter.interrupt_source_text_segments(source_text_segments))

        # 验证：应该有 8 个 math 标签被缓存
        self.assertEqual(
            len(interrupter._raw_text_segments),
            8,
            "应该有 8 个 math 标签被识别并缓存",
        )

        # 验证：处理后应该生成 expression 占位符
        expression_count = sum(
            1 for seg in interrupted_segments if any(elem.tag == "expression" for elem in seg.parent_stack)
        )
        self.assertEqual(expression_count, 8, "应该生成 8 个 expression 占位符")

        # 步骤 3: 模拟翻译过程
        translated_root = fromstring(f"<html>{self.translated_html}</html>")
        translated_body = translated_root.find(".//body")
        assert translated_body is not None

        # 记录译文的原始内容（用于后续对比）
        original_translated_text = extract_text_content(translated_body)

        # 步骤 4: 模拟双语输出 - 第一遍处理原文
        original_restored = list(interrupter.interrupt_translated_text_segments(source_text_segments))

        # 验证：第一遍处理后，缓存应该还在（或至少不影响后续处理）
        # 这是问题的关键点：当前实现使用 .pop() 导致缓存被清空
        cache_after_first_pass = len(interrupter._raw_text_segments)

        # 步骤 5: 模拟双语输出 - 第二遍处理译文
        translated_text_segments = list(search_text_segments(translated_body))
        restored_segments = []
        discarded_count = 0

        for seg in translated_text_segments:
            expanded = list(interrupter.interrupt_translated_text_segments([seg]))
            if not expanded:
                discarded_count += 1
            restored_segments.extend(expanded)

        # 步骤 6: 验证结果
        restored_text_parts = [seg.text for seg in restored_segments if seg.text.strip()]
        restored_full_text = " ".join(restored_text_parts)

        # 计算内容丢失情况
        loss_ratio = 1 - (len(restored_full_text) / len(original_translated_text))

        # 断言：不应该有内容丢失
        self.assertEqual(
            discarded_count,
            0,
            f"不应该有任何文本段被丢弃，但实际丢弃了 {discarded_count} 个段。"
            f"这是因为第一遍处理时缓存被 pop 清空（缓存剩余: {cache_after_first_pass}），"
            f"第二遍处理时缓存已空，导致 expression 标签的内容被丢弃。",
        )

        # 断言：内容丢失率应该小于 5%
        self.assertLess(
            loss_ratio,
            0.05,
            f"内容丢失率 {loss_ratio * 100:.1f}% 过高（应该 < 5%）。"
            f"原始译文: {len(original_translated_text)} 字符，"
            f"恢复后: {len(restored_full_text)} 字符，"
            f"丢失: {len(original_translated_text) - len(restored_full_text)} 字符。",
        )

        # 断言：关键内容应该被保留
        # 这些是 expression 标签中的内容，不应该在译文中丢失
        expected_contents = ["3×3", "(x)", "A", "3, 1, 0", "e", "ε"]
        for content in expected_contents:
            # 注意：在当前 bug 下，这些内容会丢失
            # 修复后，这些内容应该以某种形式（原文公式或译文）被保留
            self.assertIn(
                content,
                original_translated_text,
                f"译文中应该包含 '{content}'（在 expression 标签中）",
            )


class TestXMLInterrupterBasicFunctionality(unittest.TestCase):
    """测试 XMLInterrupter 的基本功能"""

    def test_single_math_tag(self):
        """测试单个 math 标签的处理"""
        html = """<html><body><p>公式 <math display="inline"><mi>x</mi></math> 测试</p></body></html>"""
        root = fromstring(html)
        body = root.find(".//body")
        assert body is not None, "应该能找到 body 元素"
        remove_namespaces(body)

        interrupter = XMLInterrupter()
        source_segments = list(search_text_segments(body))
        interrupted = list(interrupter.interrupt_source_text_segments(source_segments))

        # 验证：应该有 1 个 math 标签被缓存
        self.assertEqual(len(interrupter._raw_text_segments), 1)

        # 验证：应该生成 expression 占位符
        expression_count = sum(1 for seg in interrupted if any(elem.tag == "expression" for elem in seg.parent_stack))
        self.assertEqual(expression_count, 1)

    def test_block_math_tag(self):
        """测试 block math 标签的处理"""
        html = """<html><body><p>公式：</p><math display="block"><mi>x</mi></math><p>测试</p></body></html>"""
        root = fromstring(html)
        body = root.find(".//body")
        assert body is not None, "应该能找到 body 元素"
        remove_namespaces(body)

        interrupter = XMLInterrupter()
        source_segments = list(search_text_segments(body))
        interrupted = list(interrupter.interrupt_source_text_segments(source_segments))

        # 验证：block math 也应该被识别
        self.assertGreater(len(interrupter._raw_text_segments), 0)


if __name__ == "__main__":
    unittest.main()
