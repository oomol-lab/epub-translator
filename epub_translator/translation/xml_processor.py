from collections.abc import Generator
from dataclasses import dataclass
from xml.etree.ElementTree import Element

from ..utils import normalize_whitespace
from ..xml import iter_with_stack
from .format import ID_KEY
from .math import xml_to_latex

_MATH_TAG = "math"
_EXPRESSION_TAG = "expression"


@dataclass
class _Node:
    id: int
    raw: Element
    processed: Element
    target: Element


class XMLProcessor:
    def __init__(self, root: Element) -> None:
        self._raw2node: dict[int, _Node] = {}
        self._root: _Node | None = self._process(root)
        self._id2node: dict[int, _Node] = self._fill_id_for_nodes(self._root)

    def _process(self, element: Element) -> _Node | None:
        target = Element(element.tag, element.attrib)
        if element.tag == _MATH_TAG:
            processed: Element = Element(_EXPRESSION_TAG)
            processed.text = xml_to_latex(element)
        else:
            processed: Element = Element(element.tag)
            processed.text = element.text
            previous_element: Element | None = None

            for child in element:
                child_node = self._process(child)
                if child_node is not None:
                    child_processed = child_node.processed
                    processed.append(child_processed)
                    child_processed.tail = child.tail
                    previous_element = child_processed
                elif child.tail:
                    if previous_element is None:
                        processed.text = (processed.text or "") + child.tail
                    else:
                        previous_element.tail = (previous_element.tail or "") + child.tail

        if len(processed) == 0 and not processed.text:
            return None

        node = _Node(
            id=-1,  # placeholder
            raw=element,
            processed=processed,
            target=target,
        )
        self._raw2node[id(element)] = node
        return node

    def _fill_id_for_nodes(self, root: _Node | None) -> dict[int, _Node]:
        id2node: dict[int, _Node] = {}
        if root:
            next_id = 1
            for node in self._iter_nodes(root):
                node.id = next_id
                node.processed.set(ID_KEY, str(next_id))
                id2node[next_id] = node
                next_id += 1
        return id2node

    @property
    def processed(self) -> Element | None:
        if self._root is None:
            return None
        return self._root.processed

    def fill(self, formatted_root_element: Element) -> Element | None:
        if self._root is None:
            return None

        formatted_elements: dict[int, Element] = {}
        for _, element in iter_with_stack(formatted_root_element):
            if element.tag == _EXPRESSION_TAG:
                continue
            node_id = self._node_id(element)
            if node_id >= 0:
                formatted_elements[node_id] = element

        for node in self._iter_nodes(self._root):
            formatted_element = formatted_elements.get(node.id, None)
            if formatted_element is None:
                continue
            node.target.text = self._normalize_target_text(formatted_element.text)
            node.target.tail = self._normalize_target_text(formatted_element.tail)

        for node in self._iter_nodes(self._root):
            for child_processed in node.processed:
                node_id = self._node_id(child_processed)
                child_node = self._id2node.get(node_id, None)
                if child_node is not None:
                    node.target.append(child_node.target)

        return self._root.target

    def _node_id(self, element: Element) -> int:
        str_id = element.get(ID_KEY, None)
        if str_id is None:
            return -1
        try:
            return int(str_id)
        except ValueError:
            return -1

    def _iter_nodes(self, node: _Node) -> Generator[_Node, None, None]:
        yield node
        for raw_child in node.raw:
            child_node = self._raw2node.get(id(raw_child), None)
            if child_node is not None:
                yield from self._iter_nodes(child_node)

    def _normalize_target_text(self, text: str | None) -> str | None:
        if text is None:
            return None
        return normalize_whitespace(text)
