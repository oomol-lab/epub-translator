from xml.etree.ElementTree import Element

from ..xml import clone_element, find_first, plain_text


class Chapter:
    def __init__(self, root: Element) -> None:
        self._root: Element = root
        self._paragraph_items: list[tuple[Element, Paragraph]] = []
        for child in find_first(self._root, "body") or ():
            if plain_text(child).strip():
                self._paragraph_items.append((child, Paragraph(child)))

    @property
    def element(self) -> Element:
        return self._root

    @property
    def paragraphs(self) -> list["Paragraph"]:
        return [p for _, p in self._paragraph_items]

    def replace_submit(self) -> "Chapter":
        for raw_element, paragraph in self._paragraph_items:
            processed = paragraph.processed_element
            if processed is not None:
                index = self._index_of_raw_element(raw_element)
                self._root.remove(raw_element)
                self._root.insert(index, processed)
        return self

    def append_submit(self) -> "Chapter":
        for raw_element, paragraph in self._paragraph_items:
            processed = paragraph.processed_element
            if processed is not None:
                index = self._index_of_raw_element(raw_element)
                self._root.insert(index + 1, processed)
        return self

    def _index_of_raw_element(self, element: Element) -> int:
        for i, (raw_element, _) in enumerate(self._paragraph_items):
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
