from xml.etree.ElementTree import Element

from ..xml import clone_element, find_first, plain_text

_ParagraphsInfo = tuple[Element, list[tuple[Element, "Paragraph"]]]


class Chapter:
    def __init__(self, root: Element) -> None:
        self._root: Element = root
        self._paragraphs_info: _ParagraphsInfo | None = None
        parent = find_first(self._root, "body")
        if parent is not None:
            items: list[tuple[Element, Paragraph]] = []
            for child in parent:
                if plain_text(child).strip():
                    items.append((child, Paragraph(child)))
            self._paragraphs_info = (parent, items)

    @property
    def element(self) -> Element:
        return self._root

    @property
    def paragraphs(self) -> list["Paragraph"]:
        paragraphs_info = self._paragraphs_info
        if paragraphs_info is None:
            return []
        else:
            return [p for _, p in paragraphs_info[1]]

    def replace_submit(self) -> "Chapter":
        paragraphs_info = self._paragraphs_info
        if paragraphs_info is None:
            return self
        parent, items = paragraphs_info
        for raw_element, paragraph in items:
            processed = paragraph.processed_element
            if processed is not None:
                index = self._index_of_raw_element(items, raw_element)
                parent.remove(raw_element)
                parent.insert(index, processed)
        return self

    def append_submit(self) -> "Chapter":
        paragraphs_info = self._paragraphs_info
        if paragraphs_info is None:
            return self
        parent, items = paragraphs_info
        for raw_element, paragraph in items:
            processed = paragraph.processed_element
            if processed is not None:
                index = self._index_of_raw_element(items, raw_element)
                parent.insert(index + 1, processed)
        return self

    def _index_of_raw_element(self, items: list[tuple[Element, "Paragraph"]], element: Element) -> int:
        for i, (raw_element, _) in enumerate(items):
            if raw_element == element:
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
