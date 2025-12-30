from collections.abc import Generator, Iterable, Iterator
from enum import Enum, auto
from xml.etree.ElementTree import Element

from tiktoken import Encoding

from .utils import expand_left_element_texts, expand_right_element_texts, normalize_text_in_element


def group_fragmented_elements(
    encoding: Encoding,
    elements: Iterable[Element],
    group_max_tokens: int,
) -> Generator[list[Element], None, None]:
    remain_tokens_count: int = group_max_tokens
    elements_buffer: list[Element] = []

    for element in elements:
        if remain_tokens_count <= 0:
            remain_tokens_count = group_max_tokens
            if elements_buffer:
                yield elements_buffer
                elements_buffer = []

        counter = _XMLCounter(encoding, element)
        cost_tokens_count = counter.advance_tokens(remain_tokens_count)
        remain_tokens_count -= cost_tokens_count
        if not counter.can_advance():
            elements_buffer.append(element)
            continue

        if elements_buffer:
            yield elements_buffer
            elements_buffer = []

        remain_tokens_count = group_max_tokens - cost_tokens_count
        cost_tokens_count = counter.advance_tokens(remain_tokens_count)
        if not counter.can_advance():
            elements_buffer.append(element)
            remain_tokens_count -= cost_tokens_count
            continue

        remain_tokens_count = group_max_tokens
        yield [element]

    if elements_buffer:
        yield elements_buffer


class _TextItemKind(Enum):
    TEXT = auto()
    XML_TAG = auto()


class _XMLCounter:
    def __init__(self, encoding: Encoding, root: Element) -> None:
        self._encoding: Encoding = encoding
        self._text_iter: Iterator[str] = iter(self._expand_texts(root))
        self._remain_tokens_count: int = 0
        self._next_text_buffer: str | None = None

    def can_advance(self) -> bool:
        if self._remain_tokens_count > 0:
            return True
        if self._next_text_buffer is None:
            self._next_text_buffer = next(self._text_iter, None)
        return self._next_text_buffer is not None

    def _expand_texts(self, element: Element) -> Generator[str, None, None]:
        xml_tags_buffer: list[str] = []  # 这类过于碎片化，需拼凑避免 encoding 失效
        for kind, text in self._expand_text_items(element):
            if kind == _TextItemKind.XML_TAG:
                xml_tags_buffer.append(text)
            elif kind == _TextItemKind.TEXT:
                if xml_tags_buffer:
                    yield "".join(xml_tags_buffer)
                    xml_tags_buffer = []
                yield text
        if xml_tags_buffer:
            yield "".join(xml_tags_buffer)

    def _expand_text_items(self, element: Element) -> Generator[tuple[_TextItemKind, str], None, None]:
        for text in expand_left_element_texts(element):
            yield _TextItemKind.XML_TAG, text

        text = normalize_text_in_element(element.text)
        if text is not None:
            yield _TextItemKind.TEXT, text
        for child in element:
            yield from self._expand_text_items(child)
            tail = normalize_text_in_element(child.tail)
            if tail is not None:
                yield _TextItemKind.TEXT, tail

        for text in expand_right_element_texts(element):
            yield _TextItemKind.XML_TAG, text

    def advance_tokens(self, max_tokens_count: int) -> int:
        tokens_count: int = 0
        while tokens_count < max_tokens_count:
            if self._remain_tokens_count > 0:
                will_count_tokens = max_tokens_count - tokens_count
                if will_count_tokens > self._remain_tokens_count:
                    tokens_count += self._remain_tokens_count
                    self._remain_tokens_count = 0
                else:
                    tokens_count += will_count_tokens
                    self._remain_tokens_count -= will_count_tokens
                if tokens_count >= max_tokens_count:
                    break
            next_text = self._next_text()
            if next_text is None:
                break
            self._remain_tokens_count += len(self._encoding.encode(next_text))

        return tokens_count

    def _next_text(self) -> str | None:
        next_text: str | None = None
        if self._next_text_buffer is None:
            next_text = next(self._text_iter, None)
        else:
            next_text = self._next_text_buffer
            self._next_text_buffer = None
        return next_text
