from xml.etree.ElementTree import Element

from ..xml import clone_element, plain_text


class Chapter:
    def __init__(self, root: Element) -> None:
        self._root: Element = root
        self._paragraphs: list[Paragraph] = []
        for child in self._root:
            if plain_text(child).strip():
                self._paragraphs.append(Paragraph(child))

    @property
    def element(self) -> Element:
        return self._root

    @property
    def paragraphs(self) -> list["Paragraph"]:
        return self._paragraphs

    def replace_submit(self):
        for paragraph in self._paragraphs:
            processed = paragraph.processed_element
            if processed is not None:
                index = self._index_of_raw_element(paragraph.raw_element)
                self._root.remove(paragraph.raw_element)
                self._root.insert(index, processed)

    def append_submit(self):
        for paragraph in self._paragraphs:
            processed = paragraph.processed_element
            if processed is not None:
                index = self._index_of_raw_element(paragraph.raw_element)
                self._root.insert(index + 1, processed)

    def _index_of_raw_element(self, element: Element) -> int:
        for i, paragraph in enumerate(self._paragraphs):
            if paragraph.raw_element == element:
                return i
        raise ValueError("Element not found in paragraphs.")


class Paragraph:
    def __init__(self, root: Element) -> None:
        self._raw_element: Element = root
        self._processed_element: Element | None = None

    @property
    def raw_element(self) -> Element:
        return clone_element(self._raw_element)

    @property
    def processed_element(self) -> Element | None:
        return self._processed_element

    def submit(self, element: Element):
        self._processed_element = element
