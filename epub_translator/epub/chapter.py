from collections.abc import Generator
from xml.etree.ElementTree import Element

from ..xml import clone_element, find_first, plain_text


class Chapter:
    def __init__(self, root: Element) -> None:
        self._root: Element = root
        self._paragraph_items: list[tuple[Element, Element, Paragraph]] = list(
            self._search_paragraph(root),
        )

    @property
    def element(self) -> Element:
        return self._root

    @property
    def paragraphs(self) -> list["Paragraph"]:
        return [p for _, _, p in self._paragraph_items]

    def replace_submit(self) -> "Chapter":
        for parent, raw_element, paragraph in self._paragraph_items:
            processed = paragraph.processed_element
            if processed is not None:
                index = self._index_of_raw_element(parent, raw_element)
                parent.remove(raw_element)
                parent.insert(index, processed)
        return self

    def append_submit(self) -> "Chapter":
        for parent, raw_element, paragraph in self._paragraph_items:
            processed = paragraph.processed_element
            if processed is not None:
                index = self._index_of_raw_element(parent, raw_element)
                parent.insert(index + 1, processed)
        return self

    def _search_paragraph(self, root: Element) -> Generator[tuple[Element, Element, "Paragraph"], None, None]:
        body_element = find_first(root, "body")
        if body_element is None:
            return
        for child in body_element:
            if plain_text(child).strip():
                yield body_element, child, Paragraph(child)

    def _index_of_raw_element(self, parent: Element, checked_element: Element) -> int:
        for i, raw_element in enumerate(parent):
            if raw_element == checked_element:
                return i
        raise ValueError("Element not found in paragraphs.")


class Paragraph:
    def __init__(self, root: Element) -> None:
        self._raw_element: Element = root
        self._processed_element: Element | None = None

    def clone_raw(self) -> Element:
        return clone_element(self._raw_element)

    @property
    def processed_element(self) -> Element | None:
        return self._processed_element

    def submit(self, element: Element):
        self._processed_element = element
