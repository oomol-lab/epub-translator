import unittest
from xml.etree.ElementTree import Element

from epub_translator.xml_translator.format import ValidationError, format


class TestFormat(unittest.TestCase):
    """测试 format 函数的验证功能"""

    def test_valid_simple_structure(self):
        """测试简单有效的结构"""
        template_xml = """<xml>
  <p id="1">Hello World</p>
</xml>"""
        template_ele = self._parse_xml(template_xml)

        validated_text = """```XML
<xml>
  <p id="1">你好世界</p>
</xml>
```"""

        result = format(template_ele, validated_text, errors_limit=10)
        self.assertEqual(result.tag, "xml")
        p_elem = result.find(".//p[@id='1']")
        assert p_elem is not None
        self.assertEqual(p_elem.text, "你好世界")

    def test_valid_nested_structure(self):
        """测试嵌套结构"""
        template_xml = """<xml>
  <div id="1">
    <p id="2">First paragraph</p>
    <p id="3">Second paragraph</p>
  </div>
</xml>"""
        template_ele = self._parse_xml(template_xml)

        validated_text = """```XML
<xml>
  <div id="1">
    <p id="2">第一段</p>
    <p id="3">第二段</p>
  </div>
</xml>
```"""

        result = format(template_ele, validated_text, errors_limit=10)
        self.assertIsNotNone(result.find(".//p[@id='2']"))
        self.assertIsNotNone(result.find(".//p[@id='3']"))

    def test_missing_child_element_tail_text(self):
        """测试缺失子元素后面的 tail 文本（这是我们要修复的 bug）"""
        # 原文：<a id="5"> 后面有文本，<a id="6"> 后面也有文本
        template_xml = """<xml>
  <p id="4">
    Some text before.
    <a id="5">[2]</a>
    Text between id 5 and 6.
    <a id="6">[3]</a>
    Text after id 6.
  </p>
</xml>"""
        template_ele = self._parse_xml(template_xml)

        # 错误的译文：<a id="5"> 和 <a id="6"> 之间没有文本
        validated_text = """```XML
<xml>
  <p id="4">
    Some text before. [2] Text between id 5 and 6. [3] Text after id 6.
    <a id="5">[2]</a>
    <a id="6">[3]</a>
  </p>
</xml>
```"""

        # 应该抛出 ValidationError，因为 <a id="5"> 的 tail 文本缺失
        with self.assertRaises(ValidationError) as context:
            format(template_ele, validated_text, errors_limit=10)

        error_msg = str(context.exception)
        self.assertIn("missing text content after the element", error_msg)

    def test_missing_child_element_text(self):
        """测试缺失子元素前面的 text 文本"""
        # 原文：<p id="2"> 开始后有文本，然后才是 <a id="3">
        template_xml = """<xml>
  <p id="2">
    Text before link.
    <a id="3">[1]</a>
  </p>
</xml>"""
        template_ele = self._parse_xml(template_xml)

        # 错误的译文：<p id="2"> 开始后没有文本
        validated_text = """```XML
<xml>
  <p id="2">
    <a id="3">[1]</a>
  </p>
</xml>
```"""

        # 应该抛出 ValidationError
        with self.assertRaises(ValidationError) as context:
            format(template_ele, validated_text, errors_limit=10)

        error_msg = str(context.exception)
        self.assertIn("missing text content before child elements", error_msg)

    def test_extra_child_element_text(self):
        """测试多余的子元素前面的 text 文本"""
        # 原文：<p id="2"> 开始后没有文本，直接就是 <a id="3">
        template_xml = """<xml>
  <p id="2">
    <a id="3">[1]</a>
  </p>
</xml>"""
        template_ele = self._parse_xml(template_xml)

        # 错误的译文：<p id="2"> 开始后有多余的文本
        validated_text = """```XML
<xml>
  <p id="2">
    Extra text here.
    <a id="3">[1]</a>
  </p>
</xml>
```"""

        # 应该抛出 ValidationError
        with self.assertRaises(ValidationError) as context:
            format(template_ele, validated_text, errors_limit=10)

        error_msg = str(context.exception)
        self.assertIn("shouldn't have text content before child elements", error_msg)

    def test_extra_child_element_tail(self):
        """测试多余的子元素后面的 tail 文本"""
        # 原文：<a id="3"> 后面没有文本
        template_xml = """<xml>
  <p id="2">
    <a id="3">[1]</a>
  </p>
</xml>"""
        template_ele = self._parse_xml(template_xml)

        # 错误的译文：<a id="3"> 后面有多余的文本
        validated_text = """```XML
<xml>
  <p id="2">
    <a id="3">[1]</a>
    Extra tail text.
  </p>
</xml>
```"""

        # 应该抛出 ValidationError
        with self.assertRaises(ValidationError) as context:
            format(template_ele, validated_text, errors_limit=10)

        error_msg = str(context.exception)
        self.assertIn("shouldn't have text content after the element", error_msg)

    def test_complex_nested_with_correct_tail(self):
        """测试复杂嵌套结构，tail 文本正确"""
        template_xml = """<xml>
  <html id="0">
    <body id="1">
      <p id="2">
        Text before first link.
        <a id="3">[1]</a>
      </p>
      <p id="4">
        Text before second link.
        <a id="5">[2]</a>
        Text between second and third link.
        <a id="6">[3]</a>
      </p>
    </body>
  </html>
</xml>"""
        template_ele = self._parse_xml(template_xml)

        # 正确的译文结构
        validated_text = """```XML
<xml>
  <html id="0">
    <body id="1">
      <p id="2">
        Translated text before first link.
        <a id="3">[1]</a>
      </p>
      <p id="4">
        Translated text before second link.
        <a id="5">[2]</a>
        Translated text between second and third link.
        <a id="6">[3]</a>
      </p>
    </body>
  </html>
</xml>
```"""

        # 应该成功
        result = format(template_ele, validated_text, errors_limit=10)
        self.assertIsNotNone(result)

    def test_real_world_case_from_log(self):
        """测试日志文件中的真实案例"""
        template_xml = """<xml>
  <html id="0">
    <body id="1">
      <p id="4">
        拉康（Lacan，2006)将语言与享乐丧失的体验之间的最初且不可分割的这种关联称为"结扣点"。
        <a class="super" href="#mark-2" id="5">[2]</a>
        从拉康在20世纪70年代阐述的理论观点来看，我们可以发现结扣点在某种意义上已经是一个圣状。
        <a class="super" href="#mark-3" id="6">[3]</a>
      </p>
    </body>
  </html>
</xml>"""
        template_ele = self._parse_xml(template_xml)

        # 错误的译文：<a id="5"> 和 <a id="6"> 之间没有文本
        validated_text = """```XML
<xml>
  <html id="0">
    <body id="1">
      <p id="4">
        Lacan (2006) referred to this initial and inseparable connection. [2] From the theoretical perspective Lacan elaborated in the 1970s. [3]
        <a class="super" href="#mark-2" id="5">[2]</a>
        <a class="super" href="#mark-3" id="6">[3]</a>
      </p>
    </body>
  </html>
</xml>
```"""

        # 应该抛出 ValidationError
        with self.assertRaises(ValidationError) as context:
            format(template_ele, validated_text, errors_limit=10)

        error_msg = str(context.exception)
        # 应该检测到 <a id="5"> 后面缺少 tail 文本
        self.assertIn("missing text content after the element", error_msg)

    def test_whitespace_only_not_counted_as_text(self):
        """测试只有空白的文本不算作有效文本"""
        template_xml = """<xml>
  <p id="2">
    <a id="3">[1]</a>
  </p>
</xml>"""
        template_ele = self._parse_xml(template_xml)

        # 译文中只有空白，应该视为没有文本
        validated_text = """```XML
<xml>
  <p id="2">

    <a id="3">[1]</a>

  </p>
</xml>
```"""

        # 应该成功，因为只有空白不算文本
        result = format(template_ele, validated_text, errors_limit=10)
        self.assertIsNotNone(result)

    def test_lost_sub_tags(self):
        """测试丢失子标签"""
        template_xml = """<xml>
  <div id="1">
    <p id="2">First</p>
    <p id="3">Second</p>
  </div>
</xml>"""
        template_ele = self._parse_xml(template_xml)

        # 缺少 <p id="3">
        validated_text = """```XML
<xml>
  <div id="1">
    <p id="2">First translated</p>
  </div>
</xml>
```"""

        with self.assertRaises(ValidationError) as context:
            format(template_ele, validated_text, errors_limit=10)

        error_msg = str(context.exception)
        self.assertIn("lost sub-tags", error_msg)

    def test_extra_sub_tags(self):
        """测试多余子标签"""
        template_xml = """<xml>
  <div id="1">
    <p id="2">First</p>
  </div>
</xml>"""
        template_ele = self._parse_xml(template_xml)

        # 多了 <p id="3">
        validated_text = """```XML
<xml>
  <div id="1">
    <p id="2">First translated</p>
    <p id="3">Extra</p>
  </div>
</xml>
```"""

        with self.assertRaises(ValidationError) as context:
            format(template_ele, validated_text, errors_limit=10)

        error_msg = str(context.exception)
        self.assertIn("extra sub-tags", error_msg)

    def _parse_xml(self, xml_str: str) -> Element:
        """解析 XML 字符串为 Element"""
        from xml.etree.ElementTree import fromstring

        return fromstring(xml_str)


if __name__ == "__main__":
    unittest.main()
