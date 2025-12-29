from xml.etree.ElementTree import Element

from ..xml import iter_with_stack
from .text_segment import TextSegment, combine_text_segments


def submit_text_segments(element: Element, text_segments: list[TextSegment]):
    # FIXME: 当前方案不区分 text 和 tail，会将 text 错误地插入到更后面，阅读起来顺序会错乱
    grouped_map = dict(_group_text_segments(text_segments))
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


def _group_text_segments(text_segments: list[TextSegment]):
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


def _index_of_parent(parent: Element, checked_element: Element) -> int:
    for i, child in enumerate(parent):
        if child == checked_element:
            return i
    raise ValueError("Element not found in parent.")
