import re

from typing import Iterable
from xml.etree.ElementTree import fromstring, tostring, Element
from .dom_operator import read_texts, append_texts
from .empty_tags import to_xml, to_html


_FILE_HEAD_PATTERN = re.compile(r"^<\?xml.*?\?>[\s]*<!DOCTYPE.*?>")
_XMLNS_IN_TAG = re.compile(r"\{[^}]+\}")
_BRACES = re.compile(r"(\{|\})")

class HTMLFile:
  def __init__(self, file_content: str):
    match = re.match(_FILE_HEAD_PATTERN, file_content)
    xml_content = re.sub(_FILE_HEAD_PATTERN, "", to_xml(file_content))
    self._head: str = match.group() if match else None
    self._root: Element = fromstring(xml_content)
    self._xmlns: str | None = self._extract_xmlns(self._root)
    self._texts_length: int | None = None

  def _extract_xmlns(self, root: Element) -> str | None:
    root_xmlns: str | None = None
    for i, element in enumerate(_all_elements(root)):
      need_clean_xmlns = True
      match = re.match(_XMLNS_IN_TAG, element.tag)

      if match:
        xmlns = re.sub(_BRACES, "", match.group())
        if i == 0:
          root_xmlns = xmlns
        elif root_xmlns != xmlns:
          need_clean_xmlns = False
      if need_clean_xmlns:
        element.tag = re.sub(_XMLNS_IN_TAG, "", element.tag)

    return root_xmlns

  def read_texts(self) -> list[str]:
    texts = list(read_texts(self._root))
    self._texts_length = len(texts)
    return texts

  def write_texts(self, texts: Iterable[str]):
    append_texts(self._root, texts)

  @property
  def texts_length(self) -> int:
    if self._texts_length is None:
      self._texts_length = 0
      for _ in read_texts(self._root):
        self._texts_length += 1
    return self._texts_length

  @property
  def file_content(self) -> str:
    file_content: str
    if self._xmlns is None:
      file_content = tostring(self._root, encoding="unicode")
      file_content = to_html(file_content)
    else:
      root = Element(
        self._root.tag,
        attrib={**self._root.attrib, "xmlns": self._xmlns},
      )
      root.extend(self._root)
      # XHTML disable <tag/> (we need replace them with <tag></tag>)
      for element in _all_elements(root):
        if element.text is None:
          element.text = ""
      file_content = tostring(root, encoding="unicode")

    if self._head is not None:
      file_content = self._head + file_content
    return file_content

def _all_elements(parent: Element):
  yield parent
  for child in parent:
    yield from _all_elements(child)