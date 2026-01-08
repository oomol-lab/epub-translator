from collections.abc import Generator, Iterable
from typing import cast
from xml.etree.ElementTree import Element

from .segment import TextSegment
from .utils import ensure_list, normalize_whitespace

_ID_KEY = "__XML_INTERRUPTER_ID"
_MATH_TAG = "math"
_EXPRESSION_TAG = "expression"


class XMLInterrupter:
    def __init__(self) -> None:
        self._next_id: int = 1
        self._last_interrupted_id: str | None = None
        self._placeholder2interrupted: dict[int, Element] = {}
        self._raw_text_segments: dict[str, list[TextSegment]] = {}

    def interrupt_source_text_segments(
        self, text_segments: Iterable[TextSegment]
    ) -> Generator[TextSegment, None, None]:
        for text_segment in text_segments:
            yield from self._expand_source_text_segment(text_segment)

        if self._last_interrupted_id is not None:
            merged_text_segment = self._pop_and_merge_from_buffered(self._last_interrupted_id)
            if merged_text_segment:
                yield merged_text_segment

    def interrupt_translated_text_segments(
        self, text_segments: Iterable[TextSegment]
    ) -> Generator[TextSegment, None, None]:
        for text_segment in text_segments:
            yield from self._expand_translated_text_segment(text_segment)

    def interrupt_block_element(self, element: Element) -> Element:
        interrupted_element = self._placeholder2interrupted.pop(id(element), None)
        if interrupted_element is None:
            return element
        else:
            return interrupted_element

    def _expand_source_text_segment(self, text_segment: TextSegment):
        interrupted_index = self._interrupted_index(text_segment)
        interrupted_id: str | None = None

        if interrupted_index is not None:
            interrupted_element = text_segment.parent_stack[interrupted_index]
            interrupted_id = interrupted_element.get(_ID_KEY)
            if interrupted_id is None:
                interrupted_id = str(self._next_id)
                interrupted_element.set(_ID_KEY, interrupted_id)
                self._next_id += 1
            text_segments = ensure_list(
                target=self._raw_text_segments,
                key=interrupted_id,
            )
            text_segments.append(text_segment)

        if self._last_interrupted_id is not None and interrupted_id != self._last_interrupted_id:
            merged_text_segment = self._pop_and_merge_from_buffered(self._last_interrupted_id)
            if merged_text_segment:
                yield merged_text_segment

        self._last_interrupted_id = interrupted_id

        if interrupted_index is None:
            yield text_segment

    def _pop_and_merge_from_buffered(self, interrupted_id: str) -> TextSegment | None:
        merged_text_segment: TextSegment | None = None
        text_segments = self._raw_text_segments.get(interrupted_id, None)
        if text_segments:
            text_segment = text_segments[0]
            interrupted_index = cast(int, self._interrupted_index(text_segment))
            interrupted_element = text_segment.parent_stack[cast(int, interrupted_index)]
            placeholder_element = Element(
                _EXPRESSION_TAG,
                {
                    _ID_KEY: cast(str, interrupted_element.get(_ID_KEY)),
                },
            )
            raw_parent_stack = text_segment.parent_stack[:interrupted_index]
            parent_stack = raw_parent_stack + [placeholder_element]
            merged_text_segment = TextSegment(
                text="".join(t.text for t in text_segments),
                parent_stack=parent_stack,
                left_common_depth=text_segments[0].left_common_depth,
                right_common_depth=text_segments[-1].right_common_depth,
                block_depth=len(parent_stack),
                position=text_segments[0].position,
            )
            self._placeholder2interrupted[id(placeholder_element)] = interrupted_element

            # TODO: 比较难搞，先关了再说
            # parent_element: Element | None = None
            # if interrupted_index > 0:
            #     parent_element = text_segment.parent_stack[interrupted_index - 1]

            # if (
            #     not self._is_inline_math(interrupted_element)
            #     or parent_element is None
            #     or self._has_no_math_texts(parent_element)
            # ):
            #     # 区块级公式不必重复出现，出现时突兀。但行内公式穿插在译文中更有利于读者阅读顺畅。
            #     self._raw_text_segments.pop(interrupted_id, None)
            # else:
            #     for text_segment in text_segments:
            #         # 原始栈退光，仅留下相对 interrupted 元素的栈，这种格式与 translated 要求一致
            #         text_segment.left_common_depth = max(0, text_segment.left_common_depth - interrupted_index)
            #         text_segment.right_common_depth = max(0, text_segment.right_common_depth - interrupted_index)
            #         text_segment.block_depth = 1
            #         text_segment.parent_stack = text_segment.parent_stack[interrupted_index:]
            for text_segment in text_segments:
                # 原始栈退光，仅留下相对 interrupted 元素的栈，这种格式与 translated 要求一致
                text_segment.left_common_depth = max(0, text_segment.left_common_depth - interrupted_index)
                text_segment.right_common_depth = max(0, text_segment.right_common_depth - interrupted_index)
                text_segment.block_depth = 1
                text_segment.parent_stack = text_segment.parent_stack[interrupted_index:]

        return merged_text_segment

    def _interrupted_index(self, text_segment: TextSegment) -> int | None:
        interrupted_index: int | None = None
        for i, parent_element in enumerate(text_segment.parent_stack):
            if parent_element.tag == _MATH_TAG:
                interrupted_index = i
                break
        return interrupted_index

    def _expand_translated_text_segment(self, text_segment: TextSegment):
        interrupted_id = text_segment.block_parent.attrib.pop(_ID_KEY, None)
        if interrupted_id is None:
            yield text_segment
            return

        raw_text_segments = self._raw_text_segments.pop(interrupted_id, None)
        if not raw_text_segments:
            return

        raw_block = raw_text_segments[0].parent_stack[0]
        if not self._is_inline_math(raw_block):
            return

        for raw_text_segment in raw_text_segments:
            raw_text_segment.block_parent.attrib.pop(_ID_KEY, None)
            yield raw_text_segment

    def _has_no_math_texts(self, element: Element):
        if element.tag == _MATH_TAG:
            return True
        if element.text and normalize_whitespace(element.text).strip():
            return False
        for child_element in element:
            if not self._has_no_math_texts(child_element):
                return False
            if child_element.tail and normalize_whitespace(child_element.tail).strip():
                return False
        return True

    def _is_inline_math(self, element: Element) -> bool:
        if element.tag != _MATH_TAG:
            return False
        return element.get("display", "").lower() != "block"
