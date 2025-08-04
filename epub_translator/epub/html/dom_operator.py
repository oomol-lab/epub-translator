from io import StringIO
from typing import cast, Generator, Iterable
from xml.etree.ElementTree import Element
from .texts_searcher import search_texts, TextPosition


def read_texts(root: Element) -> Generator[str, None, None]:
  for element, position, _ in search_texts(root):
    if position == TextPosition.WHOLE_DOM:
      yield _plain_text(element)
    elif position == TextPosition.TEXT:
      yield cast(str, element.text)
    elif position == TextPosition.TAIL:
      yield cast(str, element.tail)

def write_texts(root: Element, texts: Iterable[str | Iterable[str] | None], append: bool):
  zip_list = list(zip(texts, search_texts(root)))
  for text, (element, position, parent) in reversed(zip_list):
    if text is None:
      continue
    if not isinstance(text, str):
      # TODO: implements split text
      text = "".join(text)
    if position == TextPosition.WHOLE_DOM:
      if parent is not None:
        _write_dom(parent, element, text, append)
    elif position == TextPosition.TEXT:
      element.text = _write_text(element.text, text, append)
    elif position == TextPosition.TAIL:
      element.tail = _write_text(element.tail, text, append)

def _write_dom(parent: Element, origin: Element, text: str, append: bool):
  if append:
    appended = Element(origin.tag, {**origin.attrib})
    for index, child in enumerate(parent):
      if child == origin:
        parent.insert(index + 1, appended)
        break
    appended.attrib.pop("id", None)
    appended.text = text
    appended.tail = origin.tail
    origin.tail = None
  else:
    for child in origin:
      origin.remove(child)
    origin.text = text

def _write_text(left: str | None, right: str, append: bool) -> str:
  if not append:
    return right
  elif left is None:
    return right
  else:
    return left + right

def _plain_text(target: Element):
  buffer = StringIO()
  for text in _iter_text(target):
    buffer.write(text)
  return buffer.getvalue()

def _iter_text(parent: Element):
  if parent.text is not None:
    yield parent.text
  for child in parent:
    yield from _iter_text(child)
  if parent.tail is not None:
    yield parent.tail