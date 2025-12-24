import io
import re
from typing import IO
from xml.etree.ElementTree import Element, fromstring, tostring

from .xml import iter_with_stack

_COMMON_NAMESPACES = {
    "http://www.w3.org/1999/xhtml": "xhtml",
    "http://www.idpf.org/2007/ops": "epub",
    "http://www.w3.org/1998/Math/MathML": "m",
    "http://purl.org/dc/elements/1.1/": "dc",
    "http://www.daisy.org/z3986/2005/ncx/": "ncx",
    "http://www.idpf.org/2007/opf": "opf",
    "http://www.w3.org/2000/svg": "svg",
    "urn:oasis:names:tc:opendocument:xmlns:container": "container",
}

_ROOT_NAMESPACES = {
    "http://www.w3.org/1999/xhtml",  # XHTML
    "http://www.daisy.org/z3986/2005/ncx/",  # NCX
    "http://www.idpf.org/2007/opf",  # OPF
    "urn:oasis:names:tc:opendocument:xmlns:container",  # Container
}

_ENCODING_PATTERN = re.compile(r'encoding\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
_FIRST_ELEMENT_PATTERN = re.compile(r"<(?![?!])[a-zA-Z]")
_NAMESPACE_IN_TAG = re.compile(r"\{([^}]+)\}")

# HTML 规定了一系列自闭标签，这些标签需要改成非自闭的，因为 EPub 格式不支持
# https://www.tutorialspoint.com/which-html-tags-are-self-closing
_EMPTY_TAGS = (
    "br",
    "hr",
    "input",
    "col",
    "base",
    "meta",
    "area",
)

_EMPTY_TAG_PATTERN = re.compile(r"<(" + "|".join(_EMPTY_TAGS) + r")(\s[^>]*?)\s*/?>")


class XMLLikeNode:
    def __init__(self, file: IO[bytes]) -> None:
        raw_content = file.read()
        self._encoding: str = _detect_encoding(raw_content)
        content = raw_content.decode(self._encoding)
        self._header, xml_content = _extract_header(content)
        try:
            self.element = fromstring(xml_content)
        except Exception as error:
            raise ValueError("Failed to parse XML-like content") from error
        self._namespaces: dict[str, str] = _extract_and_clean_namespaces(self.element)

    @property
    def encoding(self) -> str:
        return self._encoding

    @property
    def namespaces(self) -> list[str]:
        return list(self._namespaces.keys())

    def save(self, file: IO[bytes], is_html_like: bool = False) -> None:
        writer = io.TextIOWrapper(file, encoding=self._encoding, write_through=True)
        try:
            if self._header:
                writer.write(self._header)

            content = _serialize_with_namespaces(element=self.element, namespaces=self._namespaces)
            if is_html_like:
                content = re.sub(
                    pattern=_EMPTY_TAG_PATTERN,
                    repl=lambda m: f"<{m.group(1)}{m.group(2)}>",
                    string=content,
                )
            else:
                content = re.sub(
                    pattern=_EMPTY_TAG_PATTERN,
                    repl=lambda m: f"<{m.group(1)}{m.group(2)} />",
                    string=content,
                )
            writer.write(content)

        finally:
            writer.detach()


def _detect_encoding(raw_content: bytes) -> str:
    if raw_content.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    elif raw_content.startswith(b"\xff\xfe"):
        return "utf-16-le"
    elif raw_content.startswith(b"\xfe\xff"):
        return "utf-16-be"

    # 尝试从 XML 声明中提取编码：只读取前 1024 字节来查找 XML 声明
    header_bytes = raw_content[:1024]
    for try_encoding in ("utf-8", "utf-16-le", "utf-16-be", "iso-8859-1"):
        try:
            header_str = header_bytes.decode(try_encoding)
            match = _ENCODING_PATTERN.search(header_str)
            if match:
                declared_encoding = match.group(1).lower()
                try:
                    raw_content.decode(declared_encoding)
                    return declared_encoding
                except (LookupError, UnicodeDecodeError):
                    pass
        except UnicodeDecodeError:
            continue

    try:
        raw_content.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    return "iso-8859-1"


def _extract_header(content: str) -> tuple[str, str]:
    match = _FIRST_ELEMENT_PATTERN.search(content)
    if match:
        split_pos = match.start()
        header = content[:split_pos]
        xml_content = content[split_pos:]
        return header, xml_content
    return "", content


def _extract_and_clean_namespaces(element: Element):
    namespaces: dict[str, str] = {}
    for _, elem in iter_with_stack(element):
        match = _NAMESPACE_IN_TAG.match(elem.tag)
        if match:
            namespace_uri = match.group(1)
            if namespace_uri not in namespaces:
                prefix = _COMMON_NAMESPACES.get(namespace_uri, f"ns{len(namespaces)}")
                namespaces[namespace_uri] = prefix

            tag_name = elem.tag[len(match.group(0)) :]
            elem.tag = tag_name

        for attr_key in list(elem.attrib.keys()):
            match = _NAMESPACE_IN_TAG.match(attr_key)
            if match:
                namespace_uri = match.group(1)
                if namespace_uri not in namespaces:
                    prefix = _COMMON_NAMESPACES.get(namespace_uri, f"ns{len(namespaces)}")
                    namespaces[namespace_uri] = prefix

                attr_name = attr_key[len(match.group(0)) :]
                attr_value = elem.attrib.pop(attr_key)
                elem.attrib[attr_name] = attr_value
    return namespaces


def _serialize_with_namespaces(
    element: Element,
    namespaces: dict[str, str],
) -> str:
    for namespace_uri, prefix in namespaces.items():
        if namespace_uri in _ROOT_NAMESPACES:
            element.attrib["xmlns"] = namespace_uri
        else:
            element.attrib[f"xmlns:{prefix}"] = namespace_uri
    xml_string = tostring(element, encoding="unicode")
    for namespace_uri, prefix in namespaces.items():
        if namespace_uri in _ROOT_NAMESPACES:
            xml_string = xml_string.replace(f"{{{namespace_uri}}}", "")
        else:
            xml_string = xml_string.replace(f"{{{namespace_uri}}}", f"{prefix}:")
        pattern = r'\s+xmlns:(ns\d+)="' + re.escape(namespace_uri) + r'"'
        xml_string = re.sub(pattern, "", xml_string)
    return xml_string
