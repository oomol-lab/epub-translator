from xml.etree.ElementTree import Element

from ..segment import TextSegment, combine_text_segments
from ..xml import index_of_parent, iter_with_stack
from .stream_mapper import InlineSegmentMapping


def submit_text_segments(element: Element, mappings: list[InlineSegmentMapping]) -> Element:
    grouped_map = _group_text_segments(mappings)
    _append_text_segments(element, grouped_map)
    return element


def _group_text_segments(mappings: list[InlineSegmentMapping]):
    grouped_map: dict[int, list[TextSegment]] = {}
    for block_element, text_segments in mappings:
        parent_id = id(block_element)
        grouped_map[parent_id] = text_segments

    # TODO: 如下是为了清除嵌入文字的 Block，当前版本忽略了嵌入文字的 Block 概念。
    #       这是书籍中可能出现的一种情况，虽然不多见。
    #       例如，作为非叶子的块元素，它的子块元素之间会夹杂文本，当前 collect_next_inline_segment 会忽略这些文字：
    #       <div>
    #         Some text before.
    #         <!-- 只有下一行作为叶子节点的块元素内的文字会被处理 -->
    #         <div>Paragraph 1.</div>
    #         Some text in between.
    #       </div>
    for _, text_segments in mappings:
        for text_segment in text_segments:
            for parent_block in text_segment.parent_stack[: text_segment.block_depth - 1]:
                grouped_map.pop(id(parent_block), None)

    return grouped_map


def _append_text_segments(element: Element, grouped_map: dict[int, list[TextSegment]]):
    for parents, child_element in iter_with_stack(element):
        if not parents:
            continue
        grouped = grouped_map.get(id(child_element))
        if not grouped:
            continue
        parent = parents[-1]
        index = index_of_parent(parents[-1], child_element)
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
