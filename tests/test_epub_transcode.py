from xml.etree import ElementTree as ET

from epub_translator.epub.metadata import MetadataField
from epub_translator.epub.toc import Toc
from epub_translator.epub_transcode import (
    decode_metadata,
    decode_toc,
    decode_toc_list,
    encode_metadata,
    encode_toc,
    encode_toc_list,
)


class TestEncodeToc:
    """测试 Toc 对象的编码"""

    def test_encode_simple_toc(self):
        """测试编码简单的 Toc 对象"""
        toc = Toc(
            title="Chapter 1",
            href="chapter1.xhtml",
            fragment="section1",
            id="ch1",
        )

        elem = encode_toc(toc)

        assert elem.tag == "toc-item"
        assert elem.get("href") == "chapter1.xhtml"
        assert elem.get("fragment") == "section1"
        assert elem.get("id") == "ch1"

        title_elem = elem.find("title")
        assert title_elem is not None
        assert title_elem.text == "Chapter 1"

    def test_encode_toc_without_optional_fields(self):
        """测试编码没有可选字段的 Toc 对象"""
        toc = Toc(title="Introduction")

        elem = encode_toc(toc)

        assert elem.tag == "toc-item"
        assert elem.get("href") is None
        assert elem.get("fragment") is None
        assert elem.get("id") is None

        title_elem = elem.find("title")
        assert title_elem is not None
        assert title_elem.text == "Introduction"

    def test_encode_nested_toc(self):
        """测试编码嵌套的 Toc 对象"""
        toc = Toc(
            title="Part 1",
            href="part1.xhtml",
            id="part1",
            children=[
                Toc(title="Chapter 1", href="ch1.xhtml", id="ch1"),
                Toc(title="Chapter 2", href="ch2.xhtml", id="ch2"),
            ],
        )

        elem = encode_toc(toc)

        assert elem.tag == "toc-item"
        assert elem.get("href") == "part1.xhtml"

        title_elem = elem.find("title")
        assert title_elem is not None
        assert title_elem.text == "Part 1"

        # 验证子节点
        child_elems = elem.findall("toc-item")
        assert len(child_elems) == 2

        child_0_title = child_elems[0].find("title")
        assert child_0_title is not None
        assert child_0_title.text == "Chapter 1"
        assert child_elems[0].get("href") == "ch1.xhtml"

        child_1_title = child_elems[1].find("title")
        assert child_1_title is not None
        assert child_1_title.text == "Chapter 2"
        assert child_elems[1].get("href") == "ch2.xhtml"

    def test_encode_deeply_nested_toc(self):
        """测试编码多层嵌套的 Toc 对象"""
        toc = Toc(
            title="Book",
            children=[
                Toc(
                    title="Part 1",
                    children=[
                        Toc(title="Chapter 1"),
                        Toc(title="Chapter 2"),
                    ],
                ),
                Toc(
                    title="Part 2",
                    children=[
                        Toc(title="Chapter 3"),
                    ],
                ),
            ],
        )

        elem = encode_toc(toc)

        # 验证根节点
        root_title = elem.find("title")
        assert root_title is not None
        assert root_title.text == "Book"

        # 验证第一层子节点
        part_elems = elem.findall("toc-item")
        assert len(part_elems) == 2

        part_0_title = part_elems[0].find("title")
        assert part_0_title is not None
        assert part_0_title.text == "Part 1"

        part_1_title = part_elems[1].find("title")
        assert part_1_title is not None
        assert part_1_title.text == "Part 2"

        # 验证第二层子节点
        chapter_elems = part_elems[0].findall("toc-item")
        assert len(chapter_elems) == 2

        ch_0_title = chapter_elems[0].find("title")
        assert ch_0_title is not None
        assert ch_0_title.text == "Chapter 1"

        ch_1_title = chapter_elems[1].find("title")
        assert ch_1_title is not None
        assert ch_1_title.text == "Chapter 2"


class TestDecodeToc:
    """测试 Toc 对象的解码"""

    def test_decode_simple_toc(self):
        """测试解码简单的 Toc XML"""
        xml_str = """
        <toc-item href="chapter1.xhtml" fragment="section1" id="ch1">
            <title>Chapter 1</title>
        </toc-item>
        """
        elem = ET.fromstring(xml_str)
        toc = decode_toc(elem)

        assert toc.title == "Chapter 1"
        assert toc.href == "chapter1.xhtml"
        assert toc.fragment == "section1"
        assert toc.id == "ch1"
        assert len(toc.children) == 0

    def test_decode_toc_without_optional_fields(self):
        """测试解码没有可选字段的 Toc XML"""
        xml_str = """
        <toc-item>
            <title>Introduction</title>
        </toc-item>
        """
        elem = ET.fromstring(xml_str)
        toc = decode_toc(elem)

        assert toc.title == "Introduction"
        assert toc.href is None
        assert toc.fragment is None
        assert toc.id is None
        assert len(toc.children) == 0

    def test_decode_nested_toc(self):
        """测试解码嵌套的 Toc XML"""
        xml_str = """
        <toc-item href="part1.xhtml" id="part1">
            <title>Part 1</title>
            <toc-item href="ch1.xhtml" id="ch1">
                <title>Chapter 1</title>
            </toc-item>
            <toc-item href="ch2.xhtml" id="ch2">
                <title>Chapter 2</title>
            </toc-item>
        </toc-item>
        """
        elem = ET.fromstring(xml_str)
        toc = decode_toc(elem)

        assert toc.title == "Part 1"
        assert toc.href == "part1.xhtml"
        assert len(toc.children) == 2

        assert toc.children[0].title == "Chapter 1"
        assert toc.children[0].href == "ch1.xhtml"

        assert toc.children[1].title == "Chapter 2"
        assert toc.children[1].href == "ch2.xhtml"


class TestTocRoundTrip:
    """测试 Toc 编码和解码的往返一致性"""

    def test_simple_toc_roundtrip(self):
        """测试简单 Toc 的往返"""
        original = Toc(
            title="Chapter 1",
            href="chapter1.xhtml",
            fragment="section1",
            id="ch1",
        )

        elem = encode_toc(original)
        decoded = decode_toc(elem)

        assert decoded.title == original.title
        assert decoded.href == original.href
        assert decoded.fragment == original.fragment
        assert decoded.id == original.id
        assert len(decoded.children) == len(original.children)

    def test_nested_toc_roundtrip(self):
        """测试嵌套 Toc 的往返"""
        original = Toc(
            title="Part 1",
            href="part1.xhtml",
            id="part1",
            children=[
                Toc(title="Chapter 1", href="ch1.xhtml", id="ch1"),
                Toc(
                    title="Chapter 2",
                    href="ch2.xhtml",
                    id="ch2",
                    children=[
                        Toc(title="Section 2.1", href="ch2.xhtml", fragment="s2-1"),
                    ],
                ),
            ],
        )

        elem = encode_toc(original)
        decoded = decode_toc(elem)

        def compare_toc(t1: Toc, t2: Toc):
            assert t1.title == t2.title
            assert t1.href == t2.href
            assert t1.fragment == t2.fragment
            assert t1.id == t2.id
            assert len(t1.children) == len(t2.children)
            for c1, c2 in zip(t1.children, t2.children):
                compare_toc(c1, c2)

        compare_toc(original, decoded)

    def test_toc_list_roundtrip(self):
        """测试 Toc 列表的往返"""
        original_list = [
            Toc(title="Chapter 1", href="ch1.xhtml", id="ch1"),
            Toc(title="Chapter 2", href="ch2.xhtml", id="ch2"),
            Toc(
                title="Part 1",
                children=[
                    Toc(title="Chapter 3", href="ch3.xhtml"),
                ],
            ),
        ]

        elem = encode_toc_list(original_list)
        decoded_list = decode_toc_list(elem)

        assert len(decoded_list) == len(original_list)
        assert decoded_list[0].title == "Chapter 1"
        assert decoded_list[1].title == "Chapter 2"
        assert decoded_list[2].title == "Part 1"
        assert len(decoded_list[2].children) == 1
        assert decoded_list[2].children[0].title == "Chapter 3"


class TestEncodeMetadata:
    """测试 MetadataField 列表的编码"""

    def test_encode_single_field(self):
        """测试编码单个元数据字段"""
        fields = [MetadataField(tag_name="title", text="The Little Prince")]

        elem = encode_metadata(fields)

        assert elem.tag == "metadata-list"
        field_elems = elem.findall("field")
        assert len(field_elems) == 1

        assert field_elems[0].get("tag") == "title"
        assert field_elems[0].text == "The Little Prince"

    def test_encode_multiple_fields(self):
        """测试编码多个元数据字段"""
        fields = [
            MetadataField(tag_name="title", text="The Little Prince"),
            MetadataField(tag_name="creator", text="Antoine de Saint-Exupéry"),
            MetadataField(tag_name="publisher", text="Houghton Mifflin"),
            MetadataField(tag_name="subject", text="Fiction"),
        ]

        elem = encode_metadata(fields)

        assert elem.tag == "metadata-list"
        field_elems = elem.findall("field")
        assert len(field_elems) == 4

        assert field_elems[0].get("tag") == "title"
        assert field_elems[0].text == "The Little Prince"

        assert field_elems[1].get("tag") == "creator"
        assert field_elems[1].text == "Antoine de Saint-Exupéry"

        assert field_elems[2].get("tag") == "publisher"
        assert field_elems[2].text == "Houghton Mifflin"

        assert field_elems[3].get("tag") == "subject"
        assert field_elems[3].text == "Fiction"

    def test_encode_multiple_same_tag(self):
        """测试编码多个相同标签的字段"""
        fields = [
            MetadataField(tag_name="creator", text="Author 1"),
            MetadataField(tag_name="creator", text="Author 2"),
            MetadataField(tag_name="title", text="Book Title"),
        ]

        elem = encode_metadata(fields)

        field_elems = elem.findall("field")
        assert len(field_elems) == 3

        assert field_elems[0].get("tag") == "creator"
        assert field_elems[0].text == "Author 1"

        assert field_elems[1].get("tag") == "creator"
        assert field_elems[1].text == "Author 2"

        assert field_elems[2].get("tag") == "title"
        assert field_elems[2].text == "Book Title"

    def test_encode_empty_list(self):
        """测试编码空列表"""
        fields = []

        elem = encode_metadata(fields)

        assert elem.tag == "metadata-list"
        field_elems = elem.findall("field")
        assert len(field_elems) == 0


class TestDecodeMetadata:
    """测试 MetadataField 列表的解码"""

    def test_decode_single_field(self):
        """测试解码单个元数据字段"""
        xml_str = """
        <metadata-list>
            <field tag="title">The Little Prince</field>
        </metadata-list>
        """
        elem = ET.fromstring(xml_str)
        fields = decode_metadata(elem)

        assert len(fields) == 1
        assert fields[0].tag_name == "title"
        assert fields[0].text == "The Little Prince"

    def test_decode_multiple_fields(self):
        """测试解码多个元数据字段"""
        xml_str = """
        <metadata-list>
            <field tag="title">The Little Prince</field>
            <field tag="creator">Antoine de Saint-Exupéry</field>
            <field tag="publisher">Houghton Mifflin</field>
        </metadata-list>
        """
        elem = ET.fromstring(xml_str)
        fields = decode_metadata(elem)

        assert len(fields) == 3
        assert fields[0].tag_name == "title"
        assert fields[0].text == "The Little Prince"
        assert fields[1].tag_name == "creator"
        assert fields[1].text == "Antoine de Saint-Exupéry"
        assert fields[2].tag_name == "publisher"
        assert fields[2].text == "Houghton Mifflin"

    def test_decode_empty_list(self):
        """测试解码空列表"""
        xml_str = "<metadata-list></metadata-list>"
        elem = ET.fromstring(xml_str)
        fields = decode_metadata(elem)

        assert len(fields) == 0


class TestMetadataRoundTrip:
    """测试 MetadataField 编码和解码的往返一致性"""

    def test_single_field_roundtrip(self):
        """测试单个字段的往返"""
        original = [MetadataField(tag_name="title", text="Test Title")]

        elem = encode_metadata(original)
        decoded = decode_metadata(elem)

        assert len(decoded) == len(original)
        assert decoded[0].tag_name == original[0].tag_name
        assert decoded[0].text == original[0].text

    def test_multiple_fields_roundtrip(self):
        """测试多个字段的往返"""
        original = [
            MetadataField(tag_name="title", text="The Little Prince"),
            MetadataField(tag_name="creator", text="Antoine de Saint-Exupéry"),
            MetadataField(tag_name="creator", text="Richard Howard"),
            MetadataField(tag_name="publisher", text="Houghton Mifflin Harcourt"),
            MetadataField(tag_name="subject", text="Fiction"),
        ]

        elem = encode_metadata(original)
        decoded = decode_metadata(elem)

        assert len(decoded) == len(original)
        for orig, dec in zip(original, decoded):
            assert dec.tag_name == orig.tag_name
            assert dec.text == orig.text

    def test_special_characters_roundtrip(self):
        """测试特殊字符的往返"""
        original = [
            MetadataField(tag_name="title", text='Title with <special> & "quotes" & 中文'),
            MetadataField(tag_name="description", text="Line 1\nLine 2\nLine 3"),
        ]

        elem = encode_metadata(original)
        decoded = decode_metadata(elem)

        assert len(decoded) == len(original)
        assert decoded[0].text == original[0].text
        assert decoded[1].text == original[1].text


class TestEdgeCases:
    """测试边缘情况"""

    def test_toc_with_special_characters(self):
        """测试包含特殊字符的 Toc"""
        toc = Toc(
            title="Chapter <1> & \"Quotes\" & 'Apostrophes' & 测试",
            href="special.xhtml",
            id="special-1",
        )

        elem = encode_toc(toc)
        decoded = decode_toc(elem)

        assert decoded.title == toc.title
        assert decoded.href == toc.href
        assert decoded.id == toc.id

    def test_metadata_with_newlines(self):
        """测试包含换行符的元数据"""
        fields = [
            MetadataField(
                tag_name="description",
                text="Line 1\nLine 2\nLine 3\n\nLine 5",
            ),
        ]

        elem = encode_metadata(fields)
        decoded = decode_metadata(elem)

        assert len(decoded) == 1
        assert decoded[0].text == fields[0].text

    def test_metadata_with_long_text(self):
        """测试包含长文本的元数据"""
        long_text = "A" * 10000
        fields = [MetadataField(tag_name="description", text=long_text)]

        elem = encode_metadata(fields)
        decoded = decode_metadata(elem)

        assert len(decoded) == 1
        assert decoded[0].text == long_text
