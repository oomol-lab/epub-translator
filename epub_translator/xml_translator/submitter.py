from enum import Enum, auto
from typing import cast
from xml.etree.ElementTree import Element

from ..segment import TextSegment, combine_text_segments
from ..utils import nest
from ..xml import index_of_parent, iter_with_stack
from .stream_mapper import InlineSegmentMapping


class SubmitAction(Enum):
    Replace = auto()
    Append = auto()


class _PeakNode:
    def __init__(self, raw_element: Element, text_segments: list[TextSegment]) -> None:
        pass


class _PlatformNode:
    def __init__(
        self,
        raw_element: Element,
        items: list[tuple[list[TextSegment], "_PeakNode | _PlatformNode"]],
        tail_text_segments: list[TextSegment],
    ) -> None:
        pass


def _nest_nodes(mappings: list[InlineSegmentMapping]):
    # 需要翻译的文字会被嵌套到两种不同的结构中。
    # 最常见的的是 peak 结构，例如如下结构，没有任何子结构。可直接文本替换或追加。
    # <div>Some text <b>bold text</b> more text.</div>
    #
    # 但是还有一种少见的 platform 结构，它内部被其他 peak/platform 切割。
    #       <div>
    #         Some text before.
    #         <!-- 如下 peak 将它的阅读流切段 -->
    #         <div>Paragraph 1.</div>
    #         Some text in between.
    #       </div>
    # 如果直接对它进行替换或追加，读者阅读流会被破坏，从而读起来怪异。
    # 正是因为这种结构的存在，必须还原成树型结构，然后用特殊的方式来处理 platform 结构。
    #
    # 总之，我们假设 95% 的阅读体验由 peak 提供，但为兼顾剩下的 platform 结构，故加此步骤。
    grouped_text_segments = nest((id(e), text_segments) for e, text_segments in mappings)
    id2children: dict[int, list[int | _PeakNode | _PlatformNode]] = dict(
        (id, []) for id in grouped_text_segments.keys()
    )
    for group_id, group in grouped_text_segments.items():
        text_segment = group[0][0]
        # ignore the last one (it's self element)
        for i in range(len(text_segment.parent_stack) - 2, -1, -1):
            parent = text_segment.parent_stack[i]
            children = id2children.get(id(parent), None)
            if children is not None:
                children.append(group_id)
                break

    nodes_buffer: dict[int, _PeakNode | _PlatformNode] = {}
    while id2children:
        for group_id, children in list(id2children.items()):
            group = grouped_text_segments[group_id]
            if not children:
                id2children.pop(group_id)
                nodes_buffer[group_id] = _PeakNode(
                    raw_element=group[0][0].block_parent,
                    text_segments=[t for ts in group for t in ts],
                )
            else:
                progress_count: int = 0
                for i in range(len(children)):
                    child = children[i]
                    if not isinstance(child, int):
                        progress_count += 1
                    else:
                        child_node = nodes_buffer.get(child, None)
                        if child_node is not None:
                            children[i] = child_node
                            progress_count += 1
                if progress_count >= len(children):
                    id2children.pop(group_id)
                    nodes_buffer[group_id] = _create_platform_node(
                        group=group,
                        children=cast(list[_PeakNode | _PlatformNode], children),
                    )


def _create_platform_node(group: list[list[TextSegment]], children: list[_PeakNode | _PlatformNode]) -> _PlatformNode:
    raise NotImplementedError()


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
