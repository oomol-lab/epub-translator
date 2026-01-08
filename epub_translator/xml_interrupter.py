from collections.abc import Generator
from xml.etree.ElementTree import Element

from .segment import TextSegment
from .utils import ensure_list

_ID_KEY = "__XML_INTERRUPTER_ID"
_MATH_TAG = "math"
_EXPRESSION_TAG = "expression"


class XMLInterrupter:
    def __init__(self) -> None:
        self._next_id: int = 0
        self._raw_text_segments: dict[str, list[TextSegment]] = {}

    def interrupt_source_text_segments(self, text_segment: TextSegment) -> Generator[TextSegment, None, None]:
        block_element = text_segment.block_parent
        interrupted_id = block_element.get(_ID_KEY)
        if interrupted_id is not None:
            ensure_list(self._raw_text_segments, interrupted_id).append(text_segment)
            return

        if block_element.tag != _MATH_TAG:
            yield text_segment
            return

        interrupted_id = str(self._next_id)
        block_element.set(_ID_KEY, interrupted_id)
        parent_stack = text_segment.parent_stack[: text_segment.block_depth - 1]
        parent_stack.append(Element(_EXPRESSION_TAG, {_ID_KEY: interrupted_id}))
        self._next_id += 1

        yield TextSegment(
            text=text_segment.text,
            parent_stack=parent_stack,
            left_common_depth=text_segment.left_common_depth,
            right_common_depth=text_segment.right_common_depth,
            block_depth=len(parent_stack),
            position=text_segment.position,
        )
        ensure_list(self._raw_text_segments, interrupted_id).append(text_segment)

    def interrupt_translated_text_segments(self, text_segment: TextSegment) -> Generator[TextSegment, None, None]:
        interrupted_id = text_segment.block_parent.get(_ID_KEY)
        if interrupted_id is None:
            yield text_segment
            return

        raw_text_segments = self._raw_text_segments.pop(interrupted_id, None)
        if not raw_text_segments:
            return

        raw_block = raw_text_segments[0].block_parent
        if not self._is_inline_math(raw_block):
            # 区块级公式不必重复出现，出现时突兀。但行内公式穿插在译文中更有利于读者阅读顺畅。
            return

        translated_stack = text_segment.parent_stack[: len(text_segment.parent_stack) - text_segment.block_depth]
        for raw_text_segment in raw_text_segments:
            raw_text_segment.block_parent.attrib.pop(_ID_KEY, None)
            raw_text_segment.strip_block_parents()
            raw_text_segment.parent_stack = translated_stack + raw_text_segment.parent_stack
            yield raw_text_segment

    def _is_inline_math(self, element: Element) -> bool:
        if element.tag != _MATH_TAG:
            return False
        return element.get("display", "").lower() != "block"
