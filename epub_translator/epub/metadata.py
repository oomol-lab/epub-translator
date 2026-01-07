from dataclasses import dataclass

from .common import find_opf_path
from .zip import Zip


@dataclass
class MetadataField:
    """
    表示 EPUB OPF 文件中的元数据字段

    - tag_name: 标签名（不带命名空间）
    - text: 文本内容
    """

    tag_name: str
    text: str


# 不应该被翻译的元数据字段
SKIP_FIELDS = {
    "language",
    "identifier",
    "date",
    "meta",
    "contributor",  # Usually technical information
}


def read_metadata(zip: Zip) -> list[MetadataField]:
    """
    从 EPUB 的 OPF 文件中读取所有可翻译的元数据字段。

    返回包含标签名和文本内容的列表。
    自动过滤掉不应该翻译的字段（language, identifier, date, meta, contributor 等）。
    """
    opf_path = find_opf_path(zip)

    with zip.read(opf_path) as f:
        content = f.read()

    from xml.etree import ElementTree as ET

    root = ET.fromstring(content)

    # Find metadata element
    metadata_elem = None
    for child in root:
        if child.tag.endswith("metadata"):
            metadata_elem = child
            break

    if metadata_elem is None:
        return []

    # Collect metadata fields to translate
    fields: list[MetadataField] = []

    for elem in metadata_elem:
        # Get tag name without namespace
        tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        # Check if element has text content and should be translated
        if elem.text and elem.text.strip() and tag_name not in SKIP_FIELDS:
            fields.append(MetadataField(tag_name=tag_name, text=elem.text.strip()))

    return fields


def write_metadata(zip: Zip, fields: list[MetadataField]) -> None:
    """
    将翻译后的元数据字段写回 EPUB 的 OPF 文件。

    根据 tag_name 匹配对应的元素，并更新其文本内容。
    匹配策略：按照 tag_name 和在文件中出现的顺序依次匹配。
    """
    opf_path = find_opf_path(zip)

    with zip.read(opf_path) as f:
        content = f.read()

    from xml.etree import ElementTree as ET

    root = ET.fromstring(content)

    # Find metadata element
    metadata_elem = None
    for child in root:
        if child.tag.endswith("metadata"):
            metadata_elem = child
            break

    if metadata_elem is None:
        return

    # Build a mapping: tag_name -> list of fields with that tag_name
    fields_by_tag: dict[str, list[str]] = {}
    for field in fields:
        if field.tag_name not in fields_by_tag:
            fields_by_tag[field.tag_name] = []
        fields_by_tag[field.tag_name].append(field.text)

    # Create a counter for each tag to track which occurrence we're at
    tag_counters: dict[str, int] = {tag: 0 for tag in fields_by_tag}

    # Update elements in metadata
    for elem in metadata_elem:
        # Get tag name without namespace
        tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        # Check if this tag has translated text
        if tag_name in fields_by_tag and elem.text and elem.text.strip():
            counter = tag_counters[tag_name]
            if counter < len(fields_by_tag[tag_name]):
                # Update the text with translated version
                elem.text = fields_by_tag[tag_name][counter]
                tag_counters[tag_name] += 1

    # Write back the modified OPF file
    tree = ET.ElementTree(root)
    with zip.replace(opf_path) as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)
