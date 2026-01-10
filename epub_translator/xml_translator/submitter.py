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


def submit(element: Element, action: SubmitAction, mappings: list[InlineSegmentMapping]):
    submitter = _Submitter(
        element=element,
        action=action,
        mappings=mappings,
    )
    replaced_root = submitter.do()
    if replaced_root is not None:
        return replaced_root

    return element


@dataclass
class _Node:
    raw_element: Element
    items: list[tuple[list[TextSegment], "_Node"]]  # empty for peak, non-empty for platform
    tail_text_segments: list[TextSegment]


class _Submitter:
    def __init__(
        self,
        element: Element,
        action: SubmitAction,
        mappings: list[InlineSegmentMapping],
    ) -> None:
        self._action: SubmitAction = action
        self._nodes: list[_Node] = list(_nest_nodes(mappings))
        self._parents: dict[int, Element] = self._collect_parents(element, mappings)

    def _collect_parents(self, element: Element, mappings: list[InlineSegmentMapping]):
        ids: set[int] = set(id(e) for e, _ in mappings)
        assert id(element) not in ids
        parents_dict: dict[int, Element] = {}
        for parents, child in iter_with_stack(element):
            if parents and id(child) in ids:
                parents_dict[id(child)] = parents[-1]
        return parents_dict

    def do(self):
        replaced_root: Element | None = None

        for node in self._nodes:
            submitted = self._submit_node(node)
            if replaced_root is None:
                replaced_root = submitted

        return replaced_root

    # @return replaced root element, or None if appended to parent
    def _submit_node(self, node: _Node) -> Element | None:
        if not node.items:
            return self._submit_node_by_replace(node)
        else:
            return self._submit_node_by_append_text(node)

    def _submit_node_by_replace(self, node: _Node) -> Element | None:
        parent = self._parents.get(id(node.raw_element), None)
        if parent is None:
            return node.raw_element

        index = index_of_parent(parent, node.raw_element)
        combined = self._combine_text_segments(node.tail_text_segments)
        if combined is not None:
            parent.insert(index + 1, combined)
            combined.tail = node.raw_element.tail
            node.raw_element.tail = None
            if self._action == SubmitAction.REPLACE:
                parent.remove(node.raw_element)

        return None

    def _submit_node_by_append_text(self, node: _Node) -> Element | None:
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

        for text_segments, child_node in node.items:
            tail_element = tail_elements.get(id(child_node.raw_element), None)

            # REPLACE 模式：删除从 tail_element（或开头）到 child_element 之间的所有内容
            preserved_elements: list[Element] = []
            if self._action == SubmitAction.REPLACE:
                end_index = index_of_parent(node.raw_element, child_node.raw_element)
                preserved_elements = self._remove_elements_after_tail(
                    node_element=node.raw_element,
                    tail_element=tail_element,
                    end_index=end_index,
                )

            self._append_combined_after_tail(
                node_element=node.raw_element,
                text_segments=text_segments,
                tail_element=tail_element,
                append_to_end=False,
            )

            # 插入保留的非 inline 元素
            if preserved_elements:
                insert_position = index_of_parent(node.raw_element, child_node.raw_element)
                for i, elem in enumerate(preserved_elements):
                    node.raw_element.insert(insert_position + i, elem)

        for _, child_node in node.items:
            submitted = self._submit_node(child_node)
            if replaced_root is None:
                replaced_root = submitted

        # REPLACE 模式：删除从 last_tail_element（或开头）到末尾的所有内容
        preserved_elements: list[Element] = []
        if self._action == SubmitAction.REPLACE:
            preserved_elements = self._remove_elements_after_tail(
                node_element=node.raw_element,
                tail_element=last_tail_element,
                end_index=None,  # None 表示删除到末尾
            )

        self._append_combined_after_tail(
            node_element=node.raw_element,
            text_segments=node.tail_text_segments,
            tail_element=last_tail_element,
            append_to_end=True,
        )

        # 插入保留的非 inline 元素到末尾
        if preserved_elements:
            for elem in preserved_elements:
                node.raw_element.append(elem)

        return replaced_root

    def _remove_elements_after_tail(
        self,
        node_element: Element,
        tail_element: Element | None,
        end_index: int | None = None,
    ) -> list[Element]:
        """删除从 tail_element（或开头）到 end_index（或末尾）之间的所有元素。

        在 REPLACE 模式下，非 inline 标签会被保留并返回，以便插入到译文之后。

        参数：
        - node_element: 父元素
        - tail_element: 起始参考元素，删除它之后的内容（不包含它本身）
        - end_index: 结束索引（不包含），None 表示删除到末尾

        返回：
        - 被保留的非 inline 元素列表（保持原始顺序）
        """
        if tail_element is None:
            start_index = 0
            node_element.text = None
        else:
            start_index = index_of_parent(node_element, tail_element) + 1
            tail_element.tail = None

        if end_index is None:
            end_index = len(node_element)

        # 收集非 inline 标签
        preserved_elements: list[Element] = []
        for i in range(start_index, end_index):
            elem = node_element[i]
            if not is_inline_tag(elem.tag):
                # 保留非 inline 标签，但清空其 tail
                elem.tail = None
                preserved_elements.append(elem)

        # 倒序删除区间内的所有元素
        for i in range(end_index - 1, start_index - 1, -1):
            node_element.remove(node_element[i])

        return preserved_elements

    def _append_combined_after_tail(
        self,
        node_element: Element,
        text_segments: list[TextSegment],
        tail_element: Element | None,
        append_to_end: bool = False,
    ) -> None:
        combined = self._combine_text_segments(text_segments)
        if combined is None:
            return

        if combined.text:
            if tail_element is None:
                node_element.text = append_text_in_element(
                    origin_text=node_element.text,
                    append_text=combined.text,
                )
            else:
                tail_element.tail = append_text_in_element(
                    origin_text=tail_element.tail,
                    append_text=combined.text,
                )
        if tail_element is not None:
            insert_position = index_of_parent(node_element, tail_element) + 1
        elif append_to_end:
            insert_position = len(node_element)
        else:
            insert_position = 0

        for i, child in enumerate(combined):
            node_element.insert(insert_position + i, child)

    def _combine_text_segments(self, text_segments: list[TextSegment]) -> Element | None:
        segments = (t.strip_block_parents() for t in text_segments)
        combined = next(combine_text_segments(segments), None)
        if combined is None:
            return None
        else:
            return combined[0]


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
