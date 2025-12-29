from collections.abc import Callable
from xml.etree.ElementTree import Element

from .math import xml_to_latex

_MATH_TAG = "math"
_EXPRESSION_TAG = "expression"

_PLACEHOLDER_TAGS = frozenset((_EXPRESSION_TAG,))


def is_placeholder_tag(tag: str) -> bool:
    return tag in _PLACEHOLDER_TAGS


class Placeholder:
    def __init__(self, root: Element):
        self._raw_elements: dict[int, Element] = {}
        self._root: Element = self._replace(
            element=root,
            replace=self._replace_raw,
        )
        assert id(self._root) == id(root)

    def recover(self) -> None:
        self._replace(
            element=self._root,
            replace=self._recover_to_raw,
        )

    def _replace(self, element: Element, replace: Callable[[Element], Element | None]) -> Element:
        replaced = replace(element)
        if replaced is not None:
            return replaced
        if len(element):
            element[:] = [self._replace(child, replace) for child in element]
        return element

    def _replace_raw(self, element: Element) -> Element | None:
        if element.tag == _MATH_TAG:
            replaced = Element(_EXPRESSION_TAG)
            replaced.text = xml_to_latex(element)
            replaced.tail = element.tail
            self._raw_elements[id(replaced)] = element
            return replaced
        return None

    def _recover_to_raw(self, replaced: Element) -> Element | None:
        raw = self._raw_elements.get(id(replaced))
        if raw is not None:
            del self._raw_elements[id(replaced)]
            return raw
        return None
