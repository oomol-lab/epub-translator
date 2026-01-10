from collections.abc import Generator
from dataclasses import dataclass
from enum import Enum, auto
from xml.etree.ElementTree import Element

from ..segment import TextSegment, combine_text_segments
from ..xml import index_of_parent, iter_with_stack
from .stream_mapper import InlineSegmentMapping


class SubmitAction(Enum):
    REPLACE = auto()
    APPEND = auto()


@dataclass
class _Node:
    raw_element: Element
    items: list[tuple[list[TextSegment], "_Node"]]  # empty for peak, non-empty for platform
    tail_text_segments: list[TextSegment]


def submit(element: Element, action: SubmitAction, mappings: list[InlineSegmentMapping]):
    replaced_root: Element | None = None
    parents = _collect_parents(element, mappings)

    for node in _nest_nodes(mappings):
        submitted = _submit_node(
            node=node,
            action=action,
            parents=parents,
        )
        if replaced_root is None:
            replaced_root = submitted

    if replaced_root is not None:
        return replaced_root
    return element


def _collect_parents(element: Element, mappings: list[InlineSegmentMapping]):
    ids: set[int] = set(id(e) for e, _ in mappings)
    parents_dict: dict[int, Element] = {}
    for parents, child in iter_with_stack(element):
        if parents and id(child) in ids:
            parents_dict[id(child)] = parents[-1]
    return parents_dict


# @return replaced root element, or None if appended to parent
def _submit_node(node: _Node, action: SubmitAction, parents: dict[int, Element]) -> Element | None:
    parent = parents.get(id(node.raw_element), None)
    if parent is None:
        return node.raw_element

    if node.items:
        pass  # TODO: 处理 platform 结构
    else:
        index = index_of_parent(parent, node.raw_element)
        combined = next(
            combine_text_segments(
                segments=(t.strip_block_parents() for t in node.tail_text_segments),
            ),
            None,
        )
        if combined is not None:
            combined_element, _ = combined
            parent.insert(index + 1, combined_element)
            combined_element.tail = node.raw_element.tail
            node.raw_element.tail = None

    return None


def _nest_nodes(mappings: list[InlineSegmentMapping]) -> Generator[_Node, None, None]:
    # 需要翻译的文字会被嵌套到两种不同的结构中。
    # 最常见的的是 peak 结构，例如如下结构，没有任何子结构。可直接文本替换或追加。
    # <div>Some text <b>bold text</b> more text.</div>
    #
    # 但是还有一种少见的 platform 结构，它内部被其他 peak/platform 切割。
    #   <div>
    #     Some text before.
    #     <!-- 如下 peak 将它的阅读流切段 -->
    #     <div>Paragraph 1.</div>
    #     Some text in between.
    #   </div>
    # 如果直接对它进行替换或追加，读者阅读流会被破坏，从而读起来怪异。
    # 正是因为这种结构的存在，必须还原成树型结构，然后用特殊的方式来处理 platform 结构。
    #
    # 总之，我们假设 95% 的阅读体验由 peak 提供，但为兼顾剩下的 platform 结构，故加此步骤。
    stack: list[_Node] = []

    for block_element, text_segments in mappings:
        keep_depth: int = 0
        upwards: bool = False
        for i in range(len(stack) - 1, -1, -1):
            if stack[i].raw_element is block_element:
                keep_depth = i + 1
                upwards = True
                break

        if not upwards:
            for i in range(len(stack) - 1, -1, -1):
                if _check_includes(stack[i].raw_element, block_element):
                    keep_depth = i + 1
                    break

        while len(stack) > keep_depth:
            child_node = _fold_top_of_stack(stack)
            if not upwards and child_node is not None:
                yield child_node

        if upwards:
            stack[keep_depth - 1].tail_text_segments.extend(text_segments)
        else:
            stack.append(
                _Node(
                    raw_element=block_element,
                    items=[],
                    tail_text_segments=list(text_segments),
                )
            )
    while stack:
        child_node = _fold_top_of_stack(stack)
        if child_node is not None:
            yield child_node


def _fold_top_of_stack(stack: list[_Node]):
    child_node = stack.pop()
    if not stack:
        return child_node
    parent_node = stack[-1]
    parent_node.items.append((parent_node.tail_text_segments, child_node))
    parent_node.tail_text_segments = []
    return None


def _check_includes(parent: Element, child: Element) -> bool:
    for _, checked in iter_with_stack(parent):
        if child is checked:
            return True
    return False
