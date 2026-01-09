import unittest

from epub_translator.xml.self_closing import self_close_void_elements, unclose_void_elements


class TestSelfCloseVoidElements(unittest.TestCase):
    """测试 self_close_void_elements 函数"""

    def test_basic_void_elements(self):
        """测试基本的 void 元素转换"""
        cases = [
            ('<br>', '<br />'),
            ('<hr>', '<hr />'),
            ('<img src="test.png">', '<img src="test.png" />'),
            ('<input type="text">', '<input type="text" />'),
            ('<meta charset="utf-8">', '<meta charset="utf-8" />'),
            ('<link href="style.css" rel="stylesheet">', '<link href="style.css" rel="stylesheet" />'),
        ]

        for input_html, expected in cases:
            with self.subTest(input=input_html):
                result = self_close_void_elements(input_html)
                self.assertEqual(result, expected)

    def test_already_self_closed(self):
        """测试已经自闭合的标签不被修改"""
        cases = [
            '<br />',
            '<br/>',
            '<hr />',
            '<meta charset="utf-8" />',
            '<link href="style.css" rel="stylesheet" />',
            '<img src="test.png" />',
        ]

        for input_html in cases:
            with self.subTest(input=input_html):
                result = self_close_void_elements(input_html)
                self.assertEqual(result, input_html)

    def test_attributes_with_slash(self):
        """测试属性值中包含斜杠的情况"""
        cases = [
            ('<base href="/">', '<base href="/" />'),
            ('<base href="/path/to/file">', '<base href="/path/to/file" />'),
            ('<link href="/css/style.css" rel="stylesheet">', '<link href="/css/style.css" rel="stylesheet" />'),
            ('<img src="/images/photo.jpg" alt="Photo">', '<img src="/images/photo.jpg" alt="Photo" />'),
        ]

        for input_html, expected in cases:
            with self.subTest(input=input_html):
                result = self_close_void_elements(input_html)
                self.assertEqual(result, expected)

    def test_attributes_with_special_chars(self):
        """测试属性值中包含特殊字符的情况"""
        cases = [
            # 属性值中有 >
            ('<meta content="a>b">', '<meta content="a>b" />'),
            # 属性值中有引号（转义）
            ('<meta content="He said \\"hello\\"">', '<meta content="He said \\"hello\\"" />'),
            # 属性值中有等号
            ('<meta content="a=b">', '<meta content="a=b" />'),
        ]

        for input_html, expected in cases:
            with self.subTest(input=input_html):
                result = self_close_void_elements(input_html)
                self.assertEqual(result, expected)

    def test_attributes_with_newlines(self):
        """测试属性中包含换行的情况"""
        cases = [
            # 标签跨行
            ('''<meta
    charset="utf-8">''', '''<meta
    charset="utf-8" />'''),
            # 多个属性，每个占一行
            ('''<link
    href="style.css"
    rel="stylesheet">''', '''<link
    href="style.css"
    rel="stylesheet" />'''),
            # 属性值中有换行（虽然不常见）
            ('''<meta content="line1
line2">''', '''<meta content="line1
line2" />'''),
        ]

        for input_html, expected in cases:
            with self.subTest(input=input_html):
                result = self_close_void_elements(input_html)
                self.assertEqual(result, expected)

    def test_void_element_with_trailing_whitespace(self):
        """测试标签末尾有空白的情况"""
        cases = [
            ('<br >', '<br />'),
            ('<br  >', '<br />'),
            ('<br\t>', '<br />'),
            ('<br\n>', '<br />'),
            ('<meta charset="utf-8" >', '<meta charset="utf-8" />'),
        ]

        for input_html, expected in cases:
            with self.subTest(input=input_html):
                result = self_close_void_elements(input_html)
                self.assertEqual(result, expected)

    def test_illegal_void_element_with_content(self):
        """测试非法的 void 元素包含内容（应删除内容）"""
        cases = [
            ('<meta>invalid content</meta>', '<meta />'),
            ('<base>some content</base>', '<base />'),
            ('<link>text</link>', '<link />'),
            ('<br>text</br>', '<br />'),
            ('<hr>content</hr>', '<hr />'),
        ]

        for input_html, expected in cases:
            with self.subTest(input=input_html):
                result = self_close_void_elements(input_html)
                self.assertEqual(result, expected)

    def test_illegal_void_element_with_nested_tags(self):
        """测试非法的 void 元素包含嵌套标签（应删除所有内容）"""
        cases = [
            ('<base href="/"><span>nested</span></base>', '<base href="/" />'),
            ('<meta><div>invalid</div></meta>', '<meta />'),
            ('<link><p>text</p></link>', '<link />'),
        ]

        for input_html, expected in cases:
            with self.subTest(input=input_html):
                result = self_close_void_elements(input_html)
                self.assertEqual(result, expected)

    def test_multiple_void_elements(self):
        """测试多个 void 元素"""
        cases = [
            ('<br><br><br>', '<br /><br /><br />'),
            ('<meta name="a" content="1"><meta name="b" content="2">',
             '<meta name="a" content="1" /><meta name="b" content="2" />'),
            ('<hr><p>Text</p><hr>', '<hr /><p>Text</p><hr />'),
        ]

        for input_html, expected in cases:
            with self.subTest(input=input_html):
                result = self_close_void_elements(input_html)
                self.assertEqual(result, expected)

    def test_void_elements_in_context(self):
        """测试在完整 HTML 上下文中的 void 元素"""
        cases = [
            # 在段落中的 <br>
            ('<p>Text <br> more text</p>', '<p>Text <br /> more text</p>'),
            # 在 <head> 中的 <meta>
            ('<head><meta charset="utf-8"><title>Test</title></head>',
             '<head><meta charset="utf-8" /><title>Test</title></head>'),
            # 混合正常标签和 void 元素
            ('<div><p>Hello</p><hr><p>World</p></div>',
             '<div><p>Hello</p><hr /><p>World</p></div>'),
        ]

        for input_html, expected in cases:
            with self.subTest(input=input_html):
                result = self_close_void_elements(input_html)
                self.assertEqual(result, expected)

    def test_complex_real_world_html(self):
        """测试真实世界的复杂 HTML"""
        input_html = '''<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="/css/style.css" rel="stylesheet">
<title>Test Page</title>
</head>
<body>
<h1>Title</h1>
<p>Paragraph with <br> line break.</p>
<img src="/images/photo.jpg" alt="A photo">
<hr>
<p>Another paragraph.</p>
</body>
</html>'''

        expected = '''<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<link href="/css/style.css" rel="stylesheet" />
<title>Test Page</title>
</head>
<body>
<h1>Title</h1>
<p>Paragraph with <br /> line break.</p>
<img src="/images/photo.jpg" alt="A photo" />
<hr />
<p>Another paragraph.</p>
</body>
</html>'''

        result = self_close_void_elements(input_html)
        self.assertEqual(result, expected)

    def test_no_void_elements(self):
        """测试没有 void 元素的 HTML（应不变）"""
        input_html = '<div><p>Hello</p><span>World</span></div>'
        result = self_close_void_elements(input_html)
        self.assertEqual(result, input_html)

    def test_empty_string(self):
        """测试空字符串"""
        result = self_close_void_elements('')
        self.assertEqual(result, '')

    def test_attributes_without_quotes(self):
        """测试没有引号的属性值（虽然不规范，但可能存在）"""
        # 注意：这种情况下我们的实现可能无法完美处理，但不应该崩溃
        cases = [
            ('<meta charset=utf-8>', '<meta charset=utf-8 />'),
            ('<br class=line>', '<br class=line />'),
        ]

        for input_html, expected in cases:
            with self.subTest(input=input_html):
                result = self_close_void_elements(input_html)
                self.assertEqual(result, expected)


class TestUncloseVoidElements(unittest.TestCase):
    """测试 unclose_void_elements 函数"""

    def test_basic_unclosing(self):
        """测试基本的 void 元素取消自闭合"""
        cases = [
            ('<br />', '<br>'),
            ('<hr />', '<hr>'),
            ('<meta charset="utf-8" />', '<meta charset="utf-8">'),
            ('<link href="style.css" rel="stylesheet" />', '<link href="style.css" rel="stylesheet">'),
            ('<img src="test.png" />', '<img src="test.png">'),
        ]

        for input_html, expected in cases:
            with self.subTest(input=input_html):
                result = unclose_void_elements(input_html)
                self.assertEqual(result, expected)

    def test_unclosing_with_different_spacing(self):
        """测试不同空白格式的自闭合标签"""
        cases = [
            ('<br/>', '<br>'),  # 没有空格
            ('<br />', '<br>'),  # 一个空格
            ('<br  />', '<br>'),  # 多个空格
            ('<meta charset="utf-8"/>', '<meta charset="utf-8">'),
            ('<meta charset="utf-8" />', '<meta charset="utf-8">'),
        ]

        for input_html, expected in cases:
            with self.subTest(input=input_html):
                result = unclose_void_elements(input_html)
                self.assertEqual(result, expected)

    def test_unclosing_with_attributes(self):
        """测试带属性的标签取消自闭合"""
        cases = [
            ('<base href="/" />', '<base href="/">'),
            ('<link href="/css/style.css" rel="stylesheet" />', '<link href="/css/style.css" rel="stylesheet">'),
            ('<img src="/images/photo.jpg" alt="Photo" />', '<img src="/images/photo.jpg" alt="Photo">'),
        ]

        for input_html, expected in cases:
            with self.subTest(input=input_html):
                result = unclose_void_elements(input_html)
                self.assertEqual(result, expected)

    def test_non_void_elements_unchanged(self):
        """测试非 void 元素不受影响"""
        input_html = '<div><p>Hello</p><span /></div>'
        result = unclose_void_elements(input_html)
        # <span /> 不是 void 元素，应保持不变
        self.assertEqual(result, input_html)

    def test_mixed_content(self):
        """测试混合内容"""
        input_html = '<head><meta charset="utf-8" /><title>Test</title><link href="style.css" rel="stylesheet" /></head>'
        expected = '<head><meta charset="utf-8"><title>Test</title><link href="style.css" rel="stylesheet"></head>'
        result = unclose_void_elements(input_html)
        self.assertEqual(result, expected)

    def test_roundtrip_consistency(self):
        """测试往返转换的一致性"""
        # 对于 text/html，应该能够先 self_close 再 unclose，回到类似的形式
        original = '<br><meta charset="utf-8"><hr>'
        self_closed = self_close_void_elements(original)
        unclosed = unclose_void_elements(self_closed)

        # 结果可能有细微差别（如空格），但应该在功能上等价
        # 这里只检查关键标签存在
        self.assertIn('<br>', unclosed)
        self.assertIn('<meta charset="utf-8">', unclosed)
        self.assertIn('<hr>', unclosed)


class TestEdgeCases(unittest.TestCase):
    """测试边界情况和特殊场景"""

    def test_case_sensitivity(self):
        """测试标签名大小写（XML 区分大小写，但 HTML 不区分）"""
        # 我们的实现使用小写标签名
        cases = [
            ('<br>', '<br />'),
            ('<BR>', '<BR>'),  # 大写不会被识别为 void 元素
            ('<Br>', '<Br>'),  # 混合大小写也不会
        ]

        for input_html, expected in cases:
            with self.subTest(input=input_html):
                result = self_close_void_elements(input_html)
                self.assertEqual(result, expected)

    def test_similar_tag_names(self):
        """测试相似的标签名不被误匹配"""
        # 'br' 是 void 元素，但 'brain' 不是
        cases = [
            ('<brain>content</brain>', '<brain>content</brain>'),  # 不应修改
            ('<br><brain>test</brain>', '<br /><brain>test</brain>'),  # 只修改 br
        ]

        for input_html, expected in cases:
            with self.subTest(input=input_html):
                result = self_close_void_elements(input_html)
                self.assertEqual(result, expected)

    def test_malformed_html(self):
        """测试畸形 HTML（不应崩溃）"""
        # 这些情况下函数应该尽力处理，不崩溃
        cases = [
            '<br<',  # 不完整的标签
            '<meta charset="utf-8"',  # 缺少结束 >
            '<br>>>',  # 多余的 >
        ]

        for input_html in cases:
            with self.subTest(input=input_html):
                # 主要确保不会抛出异常
                try:
                    result = self_close_void_elements(input_html)
                    self.assertIsInstance(result, str)
                except Exception as e:
                    self.fail(f"Should not raise exception for malformed HTML: {e}")

    def test_unicode_content(self):
        """测试 Unicode 内容"""
        cases = [
            ('<meta content="中文内容">', '<meta content="中文内容" />'),
            ('<img alt="图片" src="test.png">', '<img alt="图片" src="test.png" />'),
            ('<p>文字<br>换行</p>', '<p>文字<br />换行</p>'),
        ]

        for input_html, expected in cases:
            with self.subTest(input=input_html):
                result = self_close_void_elements(input_html)
                self.assertEqual(result, expected)

    def test_very_long_attribute_value(self):
        """测试非常长的属性值"""
        long_value = "a" * 10000
        input_html = f'<meta content="{long_value}">'
        expected = f'<meta content="{long_value}" />'
        result = self_close_void_elements(input_html)
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
