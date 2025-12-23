import io
import unittest
from typing import cast
from xml.etree.ElementTree import Element

from epub_translator.tools.xml_like import XMLLikeNode


class TestXMLLikeNode(unittest.TestCase):
    """测试 XMLLikeNode 类的功能"""

    def test_preserve_encoding_utf8(self):
        """测试保留 UTF-8 编码"""
        original_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Test</title></head>
<body><p>Hello World</p></body>
</html>"""

        # 读取并修改
        input_file = io.BytesIO(original_content)
        node = XMLLikeNode(input_file)

        # 修改元素
        cast(Element, node.element.find(".//p")).text = "Modified Text"

        # 保存
        output_file = io.BytesIO()
        node.save(output_file)
        result = output_file.getvalue().decode("utf-8")

        # 验证头部保留
        self.assertIn('<?xml version="1.0" encoding="UTF-8"?>', result)
        self.assertIn("<!DOCTYPE html>", result)
        self.assertIn("Modified Text", result)

    def test_preserve_encoding_utf16(self):
        """测试保留 UTF-16 编码"""
        original_content = '<?xml version="1.0" encoding="UTF-16"?><root><item>测试</item></root>'.encode("utf-16")

        # 读取
        input_file = io.BytesIO(original_content)
        node = XMLLikeNode(input_file)

        # 验证编码检测正确
        self.assertIn("utf-16", node.encoding.lower())

    def test_clean_namespaces(self):
        """测试清理命名空间"""
        original_content = b"""<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<body>
<div xmlns:epub="http://www.idpf.org/2007/ops" epub:type="chapter">
<p>Content with namespace</p>
</div>
</body>
</html>"""

        # 读取
        input_file = io.BytesIO(original_content)
        node = XMLLikeNode(input_file)

        # 验证命名空间被提取
        self.assertTrue(len(node.namespaces) > 0)

        # 验证元素标签已清理（不再包含 {namespace}）
        for elem in node.element.iter():
            self.assertNotIn("{", elem.tag)

        # 保存
        output_file = io.BytesIO()
        node.save(output_file)
        result = output_file.getvalue().decode("utf-8")

        # 验证命名空间声明在根元素
        self.assertIn('xmlns="http://www.w3.org/1999/xhtml"', result)

    def test_preserve_header_without_xml_declaration(self):
        """测试没有 XML 声明的情况"""
        original_content = b"""<html>
<head><title>Simple</title></head>
<body><p>No declaration</p></body>
</html>"""

        # 读取并保存
        input_file = io.BytesIO(original_content)
        node = XMLLikeNode(input_file)

        output_file = io.BytesIO()
        node.save(output_file)
        result = output_file.getvalue()

        # 不应该添加 XML 声明
        self.assertNotIn(b"<?xml", result)

    def test_opf_file_with_multiple_namespaces(self):
        """测试 OPF 文件（多个命名空间）"""
        original_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:title>Book Title</dc:title>
<dc:creator>Author Name</dc:creator>
</metadata>
</package>"""

        # 读取
        input_file = io.BytesIO(original_content)
        node = XMLLikeNode(input_file)

        # 修改内容
        title_elem = node.element.find(".//title")
        if title_elem is not None:
            title_elem.text = "New Title"

        # 保存
        output_file = io.BytesIO()
        node.save(output_file)
        result = output_file.getvalue().decode("utf-8")

        # 验证命名空间声明
        self.assertIn("xmlns", result)
        # 验证内容修改成功
        if title_elem is not None:
            self.assertIn("New Title", result)

    def test_ncx_file(self):
        """测试 NCX 文件"""
        original_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
<head>
<meta name="dtb:uid" content="urn:uuid:12345"/>
</head>
<docTitle>
<text>Table of Contents</text>
</docTitle>
</ncx>"""

        # 读取
        input_file = io.BytesIO(original_content)
        node = XMLLikeNode(input_file)

        # 保存
        output_file = io.BytesIO()
        node.save(output_file)
        result = output_file.getvalue().decode("utf-8")

        # 验证 DOCTYPE 保留
        self.assertIn("<!DOCTYPE", result)
        self.assertIn("Table of Contents", result)

    def test_complex_header(self):
        """测试复杂的 header（多个处理指令、注释等）"""
        original_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<?xml-stylesheet type="text/xsl" href="style.xsl"?>
<!-- This is a comment -->
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<!-- Another comment -->
<?custom-instruction data="value"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Complex Header</title></head>
<body><p>Content</p></body>
</html>"""

        # 读取
        input_file = io.BytesIO(original_content)
        node = XMLLikeNode(input_file)

        # 保存
        output_file = io.BytesIO()
        node.save(output_file)
        result = output_file.getvalue().decode("utf-8")

        # 验证所有 header 内容都被保留
        self.assertIn('<?xml version="1.0" encoding="UTF-8"?>', result)
        self.assertIn('<?xml-stylesheet type="text/xsl" href="style.xsl"?>', result)
        self.assertIn("<!-- This is a comment -->", result)
        self.assertIn("<!DOCTYPE html", result)
        self.assertIn("<!-- Another comment -->", result)
        self.assertIn('<?custom-instruction data="value"?>', result)
        self.assertIn("Complex Header", result)

    def test_header_with_whitespace_and_newlines(self):
        """测试 header 中包含大量空白和换行的情况"""
        original_content = b"""

<?xml version="1.0" encoding="UTF-8"?>


<!DOCTYPE html>


<html>
<head><title>Test</title></head>
<body><p>Content</p></body>
</html>"""

        # 读取
        input_file = io.BytesIO(original_content)
        node = XMLLikeNode(input_file)

        # 保存
        output_file = io.BytesIO()
        node.save(output_file)
        result = output_file.getvalue().decode("utf-8")

        # 验证 header（包括所有空白）被保留
        # header 应该包含从开始到 <html 之前的所有内容
        lines = result.split("<html>")
        header_part = lines[0]
        self.assertIn("<?xml", header_part)
        self.assertIn("<!DOCTYPE", header_part)
        # 验证保留了空白行
        self.assertTrue("\n\n" in header_part)


if __name__ == "__main__":
    unittest.main()
