from collections.abc import Generator, Iterable
from dataclasses import dataclass
from enum import Enum, auto
from typing import Self
from xml.etree.ElementTree import Element

from .utils import expand_left_element_texts, expand_right_element_texts, normalize_text_in_element

# HTML inline-level elements
# Reference: https://developer.mozilla.org/en-US/docs/Web/HTML/Inline_elements
# Reference: https://developer.mozilla.org/en-US/docs/Glossary/Inline-level_content
_HTML_INLINE_TAGS = frozenset(
    [
        # Inline text semantics
        "a",
        "abbr",
        "b",
        "bdi",
        "bdo",
        "br",
        "cite",
        "code",
        "data",
        "dfn",
        "em",
        "i",
        "kbd",
        "mark",
        "q",
        "rp",
        "rt",
        "ruby",
        "s",
        "samp",
        "small",
        "span",
        "strong",
        "sub",
        "sup",
        "time",
        "u",
        "var",
        "wbr",
        # Image and multimedia
        "img",
        "svg",
        "canvas",
        "audio",
        "video",
        "map",
        "area",
        # Form elements
        "input",
        "button",
        "select",
        "textarea",
        "label",
        "output",
        "progress",
        "meter",
        # Embedded content
        "iframe",
        "embed",
        "object",
        # Other inline elements
        "script",
        "del",
        "ins",
        "slot",
    ]
)


class TextPosition(Enum):
    TEXT = auto()
    TAIL = auto()


@dataclass
class TextSegment:
    text: str
    index: int  # *.text is 0, the first *.tail is 1, and so on
    parent_stack: list[Element]
    left_common_depth: int
    right_common_depth: int
    block_depth: int
    position: TextPosition

    @property
    def root(self) -> Element:
        return self.parent_stack[0]

    @property
    def block_parent(self) -> Element:
        return self.parent_stack[self.block_depth - 1]

    @property
    def xml_text(self) -> str:
        return "".join(_expand_xml_texts(self))

    def strip_block_parents(self) -> Self:
        self.parent_stack = self.parent_stack[self.block_depth - 1 :]
        self.block_depth = 1
        return self

    def clone(self) -> "TextSegment":
        return TextSegment(
            text=self.text,
            index=self.index,
            parent_stack=list(self.parent_stack),
            left_common_depth=self.left_common_depth,
            right_common_depth=self.right_common_depth,
            block_depth=self.block_depth,
            position=self.position,
        )


def _expand_xml_texts(segment: TextSegment):
    for i in range(segment.left_common_depth, len(segment.parent_stack)):
        yield from expand_left_element_texts(segment.parent_stack[i])
    yield segment.text
    for i in range(len(segment.parent_stack) - 1, segment.right_common_depth - 1, -1):
        yield from expand_right_element_texts(segment.parent_stack[i])


def incision_between(segment1: TextSegment, segment2: TextSegment) -> tuple[int, int]:
    return (
        _incision_of(segment1, segment1.right_common_depth),
        _incision_of(segment2, segment2.left_common_depth),
    )


def _incision_of(segment: TextSegment, common_depth: int) -> int:
    block_diff: int = 0
    inline_diff: int = 0
    if common_depth >= segment.block_depth:
        inline_diff = len(segment.parent_stack) - common_depth
    else:
        block_diff = segment.block_depth - common_depth
        inline_diff = len(segment.parent_stack) - segment.block_depth
    return block_diff * 3 + inline_diff  # 数字越大越容易被拆分


def search_text_segments(root: Element) -> Generator[TextSegment, None, None]:
    generator = _search_text_segments([], root)
    text_segment = next(generator, None)
    if text_segment is None:
        return

    while True:
        next_text_segment = next(generator, None)
        if next_text_segment is None:
            break
        common_depth = _common_depth(
            stack1=text_segment.parent_stack,
            stack2=next_text_segment.parent_stack,
        )
        text_segment.right_common_depth = common_depth
        yield text_segment
        text_segment = next_text_segment
        text_segment.left_common_depth = common_depth

    yield text_segment


def _search_text_segments(stack: list[Element], element: Element) -> Generator[TextSegment, None, None]:
    text = normalize_text_in_element(element.text)
    next_stack = stack + [element]
    next_block_depth = _find_block_depth(next_stack)

    if text is not None:
        yield TextSegment(
            text=text,
            index=0,
            parent_stack=next_stack,
            left_common_depth=0,
            right_common_depth=0,
            block_depth=next_block_depth,
            position=TextPosition.TEXT,
        )
    for i, child_element in enumerate(element):
        yield from _search_text_segments(next_stack, child_element)
        child_tail = normalize_text_in_element(child_element.tail)
        if child_tail is not None:
            yield TextSegment(
                text=child_tail,
                index=i + 1,
                parent_stack=next_stack,
                left_common_depth=0,
                right_common_depth=0,
                block_depth=next_block_depth,
                position=TextPosition.TAIL,
            )


def _find_block_depth(parent_stack: list[Element]) -> int:
    index: int = 0
    for i in range(len(parent_stack) - 1, -1, -1):
        checked_tag = parent_stack[i].tag.lower()
        if checked_tag not in _HTML_INLINE_TAGS:
            index = i
            break
    return index + 1  # depth is a count not index


def combine_text_segments(segments: Iterable[TextSegment]) -> Generator[tuple[Element, dict[int, Element]], None, None]:
    stack: list[tuple[Element, Element]] = []  # (raw, generated)
    raw2generated: dict[int, Element] = {}
    last_popped: Element | None = None

    for segment in segments:
        common_depth = _common_depth(
            stack1=(raw for raw, _ in stack),
            stack2=segment.parent_stack,
        )
        if stack and common_depth == 0:
            yield stack[0][1], raw2generated
            stack = []
            raw2generated = {}
            last_popped = None

        while len(stack) > common_depth:
            last_popped = stack.pop()[1]
        while len(stack) < len(segment.parent_stack):
            last_popped = None
            index = len(stack)
            raw = segment.parent_stack[index]
            generated = Element(raw.tag, raw.attrib)
            if stack:
                _, generated_parent = stack[-1]
                generated_parent.append(generated)
            stack.append((raw, generated))
            raw2generated[id(raw)] = generated

        if last_popped is None:
            if stack:
                stack[-1][1].text = _append_element_text(
                    text=stack[-1][1].text,
                    appended=segment.text,
                )
        else:
            last_popped.tail = _append_element_text(
                text=last_popped.tail,
                appended=segment.text,
            )
    if stack:
        yield stack[0][1], raw2generated


def _common_depth(stack1: Iterable[Element], stack2: Iterable[Element]) -> int:
    common_depth: int = 0
    for parent1, parent2 in zip(stack1, stack2):
        if id(parent1) != id(parent2):
            break
        common_depth += 1
    return common_depth


def _append_element_text(text: str | None, appended: str) -> str:
    if text is None:
        return appended
    else:
        return text + appended
