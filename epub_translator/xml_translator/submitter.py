from xml.etree.ElementTree import Element

from ..segment import TextSegment, combine_text_segments
from ..xml import iter_with_stack


def submit_text_segments(element: Element, text_segments_groups: list[list[TextSegment]]) -> Element:
    grouped_map = _group_text_segments(text_segments_groups)
    _append_text_segments(element, grouped_map)
    return element


def _group_text_segments(text_segments_groups: list[list[TextSegment]]):
    grouped_map: dict[int, list[TextSegment]] = {}
    for text_segments in text_segments_groups:
        parent_id = id(text_segments[0].block_parent)
        grouped_map[parent_id] = text_segments
    return grouped_map


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
