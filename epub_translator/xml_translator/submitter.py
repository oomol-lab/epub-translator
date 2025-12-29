from collections.abc import Iterable
from xml.etree.ElementTree import Element

from ..xml import iter_with_stack
from .text_segment import TextPosition, TextSegment, combine_text_segments


def submit_text_segments(element: Element, text_segments: Iterable[TextSegment]):
    grouped_map = _group_text_segments(text_segments)
    flatten_text_segments = dict(_extract_flatten_text_segments(element, grouped_map))
    _append_text_segments(element, grouped_map)
    _replace_text_segments(element, flatten_text_segments)


def _group_text_segments(text_segments: Iterable[TextSegment]):
    grouped_map: dict[int, list[TextSegment]] = {}
    for text_segment in text_segments:
        parent_id = id(text_segment.block_parent)
        grouped = grouped_map.get(parent_id, None)
        if grouped is None:
            grouped_map[parent_id] = grouped = []
        grouped_map[parent_id].append(text_segment)
    return grouped_map


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

    if id(element) in grouped_map:
        override_parent_ids.add(id(element))  # root 不会出现在 parents 中需单独添加

    for parent_id in override_parent_ids:
        yield parent_id, grouped_map.pop(parent_id)


def _replace_text_segments(element: Element, text_segments: dict[int, list[TextSegment]]):
    for _, child_element in iter_with_stack(element):
        tail_text_segments: list[TextSegment] = []
        for text_segment in text_segments.get(id(child_element), ()):
            if text_segment.position == TextPosition.TEXT:
                child_element.text = _append_text(
                    origin_text=child_element.text,
                    append_text=text_segment.text,
                )
            elif text_segment.position == TextPosition.TAIL:
                tail_text_segments.append(text_segment)

        tail_text_segments.sort(key=lambda t: t.index)
        tail_text_segments.reverse()
        for cc_element in child_element:
            if not tail_text_segments:
                break
            if cc_element.tail is not None:
                cc_element.tail = _append_text(
                    origin_text=cc_element.tail,
                    append_text=tail_text_segments.pop().text,
                )


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


def _append_text(origin_text: str | None, append_text: str) -> str:
    if origin_text is None:
        return append_text
    else:
        return origin_text + append_text
