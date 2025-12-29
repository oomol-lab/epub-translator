from collections.abc import Iterable
from xml.etree.ElementTree import Element

from ..xml import iter_with_stack
from .text_segment import TextPosition, TextSegment, combine_text_segments


def submit_text_segments(element: Element, text_segments: Iterable[TextSegment]):
    grouped_map = dict(_group_text_segments(text_segments))
    flatten_text_segments = list(_extract_flatten_text_segments(element, grouped_map))
    _append_text_segments(element, grouped_map)
    _replace_text_segments(flatten_text_segments)


def _group_text_segments(text_segments: Iterable[TextSegment]):
    iterator = iter(text_segments)
    text_segment = next(iterator, None)
    if text_segment is None:
        return

    grouped: list[TextSegment] = [text_segment]
    while True:
        next_text_segment = next(iterator, None)
        if next_text_segment is None:
            break
        if id(text_segment.block_parent) != id(next_text_segment.block_parent):
            yield id(text_segment.block_parent), grouped
            grouped = []
        text_segment = next_text_segment
        grouped.append(text_segment)

    yield id(text_segment.block_parent), grouped


# 被覆盖的 block 表示一种偶然现象，由于它的子元素会触发 append 操作，若对它也进行 append 操作阅读顺序会混乱
# 此时只能在它的所有文本后立即接上翻译后的文本
def _extract_flatten_text_segments(element: Element, grouped_map: dict[int, list[TextSegment]]):
    override_parent_ids: set[int] = set()
    for parents, child_element in iter_with_stack(element):
        if id(child_element) not in grouped_map:
            continue
        for parent in parents[:-1]:
            parent_id = id(parent)
            if parent_id in grouped_map:
                override_parent_ids.add(parent_id)

    for parent_id in override_parent_ids:
        yield from grouped_map.pop(parent_id)


def _replace_text_segments(text_segments: Iterable[TextSegment]):
    for text_segment in text_segments:
        if text_segment.position == TextPosition.TEXT:
            text_segment.host.text = text_segment.text
        elif text_segment.position == TextPosition.TAIL:
            text_segment.host.tail = text_segment.text


def _append_text_segments(element: Element, grouped_map: dict[int, list[TextSegment]]):
    for parents, child_element in iter_with_stack(element):
        if not parents:
            continue
        grouped = grouped_map.get(id(child_element))
        if not grouped:
            continue
        parent = parents[-1]
        index = _index_of_parent(parents[-1], child_element)
        combined = next(
            combine_text_segments(
                segments=(t.strip_block_parents() for t in grouped),
            ),
            None,
        )
        if combined is not None:
            combined_element, _ = combined
            parent.insert(index + 1, combined_element)
            combined_element.tail = child_element.tail
            child_element.tail = None


def _index_of_parent(parent: Element, checked_element: Element) -> int:
    for i, child in enumerate(parent):
        if child == checked_element:
            return i
    raise ValueError("Element not found in parent.")
