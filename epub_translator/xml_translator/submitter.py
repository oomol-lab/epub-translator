from collections.abc import Generator
from dataclasses import dataclass
from enum import Enum, auto
from xml.etree.ElementTree import Element

from ..segment import TextSegment, combine_text_segments
from ..xml import append_text_in_element, index_of_parent, is_inline_tag, iter_with_stack
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
    # TODO: 尚未支持 SubmitAction.REPLACE，现在默认全是 APPEND
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
    assert id(element) not in ids
    parents_dict: dict[int, Element] = {}
    for parents, child in iter_with_stack(element):
        if parents and id(child) in ids:
            parents_dict[id(child)] = parents[-1]
    return parents_dict


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


# @return replaced root element, or None if appended to parent
def _submit_node(node: _Node, action: SubmitAction, parents: dict[int, Element]) -> Element | None:
    parent = parents.get(id(node.raw_element), None)
    if parent is None:
        return node.raw_element

    if node.items:
        return _submit_platform_node(node, action, parents)
    else:
        index = index_of_parent(parent, node.raw_element)
        combined = _combine_text_segments(node.tail_text_segments)
        if combined is not None:
            parent.insert(index + 1, combined)
            combined.tail = node.raw_element.tail
            node.raw_element.tail = None

    return None


def _submit_platform_node(node: _Node, action: SubmitAction, parents: dict[int, Element]) -> Element | None:
    replaced_root: Element | None = None
    child_nodes = dict((id(node), node) for _, node in node.items)
    last_tail_element: Element | None = None
    tail_elements: dict[int, Element] = {}

    for child_element in node.raw_element:
        child_node = child_nodes.get(id(child_element), None)
        if child_node is not None:
            if last_tail_element is not None:
                tail_elements[id(child_element)] = last_tail_element
            last_tail_element = child_element

        elif is_inline_tag(child_element.tag):
            # 与原文之间不许加载 block 元素，不好看
            last_tail_element = child_element

    for text_segments, child_node in node.items:
        tail_element = tail_elements.get(id(child_node.raw_element), None)
        combined = _combine_text_segments(text_segments)
        if combined is None:
            continue

        if combined.text:
            if tail_element is None:
                node.raw_element.text = append_text_in_element(
                    origin_text=node.raw_element.text,
                    append_text=combined.text,
                )
            else:
                tail_element.tail = append_text_in_element(
                    origin_text=tail_element.tail,
                    append_text=combined.text,
                )
        insert_position: int = 0
        if tail_element is not None:
            insert_position = index_of_parent(node.raw_element, tail_element)
            insert_position += 1  # insert after tail_element

        for i, child in enumerate(combined):
            node.raw_element.insert(i + insert_position, child)

    for _, child_node in node.items:
        submitted = _submit_node(
            node=child_node,
            action=action,
            parents=parents,
        )
        if replaced_root is None:
            replaced_root = submitted

    return replaced_root


def _combine_text_segments(text_segments: list[TextSegment]) -> Element | None:
    segments = (t.strip_block_parents() for t in text_segments)
    combined = next(combine_text_segments(segments), None)
    if combined is None:
        return None
    else:
        return combined[0]
