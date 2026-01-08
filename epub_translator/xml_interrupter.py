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
        interrupted_index = -1
        for i, parent_element in enumerate(text_segment.parent_stack):
            if parent_element.tag == _MATH_TAG:
                interrupted_index = i
                break

        if interrupted_index < 0:
            yield text_segment
            return

        interrupted_element = text_segment.parent_stack[interrupted_index]
        interrupted_id = interrupted_element.get(_ID_KEY)
        raw_parent_stack = text_segment.parent_stack[:interrupted_index]

        if interrupted_id is None:
            interrupted_id = str(self._next_id)
            interrupted_element.set(_ID_KEY, interrupted_id)
            parent_stack = raw_parent_stack + [Element(_EXPRESSION_TAG, {_ID_KEY: interrupted_id})]
            self._next_id += 1

            yield TextSegment(
                text=text_segment.text,
                parent_stack=parent_stack,
                left_common_depth=text_segment.left_common_depth,
                right_common_depth=text_segment.right_common_depth,
                block_depth=len(parent_stack),
                position=text_segment.position,
            )
        text_segments = ensure_list(
            target=self._raw_text_segments,
            key=interrupted_id,
        )
        text_segments.append(text_segment)
        text_segment.block_depth = 1
        text_segment.parent_stack = text_segment.parent_stack[interrupted_index:]

    def interrupt_translated_text_segments(self, text_segment: TextSegment) -> Generator[TextSegment, None, None]:
        interrupted_id = text_segment.block_parent.get(_ID_KEY)
        if interrupted_id is None:
            yield text_segment
            return

        raw_text_segments = self._raw_text_segments.pop(interrupted_id, None)
        if not raw_text_segments:
            return

        raw_block = raw_text_segments[0].parent_stack[0]
        if not self._is_inline_math(raw_block):
            # 区块级公式不必重复出现，出现时突兀。但行内公式穿插在译文中更有利于读者阅读顺畅。
            return

        translated_stack = text_segment.parent_stack[: len(text_segment.parent_stack) - text_segment.block_depth]
        for raw_text_segment in raw_text_segments:
            raw_text_segment.block_parent.attrib.pop(_ID_KEY, None)
            raw_text_segment.parent_stack = translated_stack + raw_text_segment.parent_stack
            yield raw_text_segment

    def _is_inline_math(self, element: Element) -> bool:
        if element.tag != _MATH_TAG:
            return False
        return element.get("display", "").lower() != "block"
