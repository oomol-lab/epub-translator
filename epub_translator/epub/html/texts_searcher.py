from typing import Generator, TypeGuard
from enum import auto, Enum
from xml.etree.ElementTree import Element


class TextPosition(Enum):
  WHOLE_DOM = auto()
  TEXT = auto()
  TAIL = auto()

# element, position, parent
TextDescription = tuple[Element, TextPosition, Element | None]

_IGNORE_TAGS = (
  "title", "link", "style", "css", "img", "script", "metadata"
)

_TEXT_LEAF_TAGS = (
  "a", "b", "br", "hr", "span", "em", "strong", "label",
)

def search_texts(element: Element, parent: Element | None = None) -> Generator[TextDescription, None, None]:
  if element.tag in _IGNORE_TAGS:
    return

  if any(c.tag not in _TEXT_LEAF_TAGS for c in element):
    if _is_not_empty_str(element.text):
      yield element, TextPosition.TEXT, parent
    for child in element:
      if child.tag in _TEXT_LEAF_TAGS:
        yield child, TextPosition.WHOLE_DOM, element
      else:
        yield from search_texts(child, element)
      if _is_not_empty_str(child.tail):
        yield child, TextPosition.TAIL, element
  else:
    yield element, TextPosition.WHOLE_DOM, parent

def _is_not_empty_str(text: str | None) -> TypeGuard[str]:
  if text is None:
    return False
  for char in text:
    if char not in (" ", "\n"):
      return True
  return False
