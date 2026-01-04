from collections.abc import Generator, Iterator
from dataclasses import dataclass
from xml.etree.ElementTree import Element

from ..utils import ensure_list, is_the_same, nest
from ..xml import append_text_in_element, iter_with_stack
from .const import ID_KEY
from .text_segment import TextSegment
from .utils import IDGenerator, element_fingerprint


@dataclass
class InlineLostIDError:
    element: Element
    stack: list[Element]


@dataclass
class InlineUnexpectedIDError:
    id: int
    element: Element


@dataclass
class InlineExceptedIDError:
    ids: list[int]


@dataclass
class InlineWrongTagCountError:
    expected_count: int
    found_elements: list[Element]
    stack: list[Element]


# @return collected InlineSegment and the next TextSegment that is not included
def collect_next_inline_segment(
    id_generator: IDGenerator,
    first_text_segment: TextSegment,
    text_segments_iter: Iterator[TextSegment],
) -> tuple["InlineSegment | None", TextSegment | None]:
    inline_segment, next_text_segment = _collect_next_inline_segment(
        first_text_segment=first_text_segment,
        text_segments_iter=text_segments_iter,
    )
    if inline_segment is not None:
        inline_segment.recreate_ids(id_generator)
    return inline_segment, next_text_segment


def _collect_next_inline_segment(
    first_text_segment: TextSegment,
    text_segments_iter: Iterator[TextSegment],
    depth: int | None = None,
) -> tuple["InlineSegment | None", TextSegment | None]:
    if depth is None:
        depth = first_text_segment.block_depth

    current_text_segment: TextSegment | None = first_text_segment
    children: list[TextSegment | InlineSegment] = []

    while current_text_segment is not None:
        text_segment_depth = len(current_text_segment.parent_stack)
        if text_segment_depth < depth:
            break
        elif text_segment_depth == depth:
            children.append(current_text_segment)
            current_text_segment = next(text_segments_iter, None)
        else:
            inline_text, current_text_segment = _collect_next_inline_segment(
                first_text_segment=current_text_segment,
                text_segments_iter=text_segments_iter,
                depth=depth + 1,
            )
            if inline_text is not None:
                children.append(inline_text)

    if not children:
        return None, current_text_segment

    inline_text = InlineSegment(
        depth=depth,
        children=children,
    )
    return inline_text, current_text_segment


class InlineSegment:
    def __init__(self, depth: int, children: list["TextSegment | InlineSegment"]) -> None:
        assert depth > 0
        self.id: int | None = None
        self._children: list[TextSegment | InlineSegment] = children
        self._parent_stack: list[Element] = children[0].parent_stack[:depth]
        self._child_tag2count: dict[str, int] = {}
        self._child_tag2ids: dict[str, list[int]] = {}  # {} value is meant that don't need to assign ids

        next_temp_id: int = 0
        terms = nest((child.parent_stack[-1].tag, child) for child in children)

        for _, child_terms in terms.items():
            if not is_the_same(  # 仅当 tag 彼此无法区分时才分配 id，以尽可能减少 id 的数量
                elements=(element_fingerprint(t.parent_stack[-1]) for t in child_terms if isinstance(t, InlineSegment)),
            ):
                for child in child_terms:
                    if isinstance(child, InlineSegment):
                        child.id = next_temp_id
                        next_temp_id += 1

    @property
    def parent_stack(self) -> list[Element]:
        return self._parent_stack

    def __iter__(self) -> Iterator[TextSegment]:
        for child in self._children:
            if isinstance(child, TextSegment):
                yield child
            elif isinstance(child, InlineSegment):
                yield from child

    def recreate_ids(self, id_generator: IDGenerator) -> None:
        for child in self._children:
            if isinstance(child, InlineSegment):
                child_tag = child.parent_stack[-1].tag
                ids = ensure_list(self._child_tag2ids, child_tag)
                if child.id is not None:
                    child.id = id_generator.next_id()
                    ids.append(child.id)
                child.recreate_ids(id_generator)
                self._child_tag2count[child_tag] = self._child_tag2count.get(child_tag, 0) + 1

    def create_element(self) -> Element:
        element = Element(self.parent_stack[-1].tag)
        previous_element: Element | None = None
        for child in self._children:
            if isinstance(child, InlineSegment):
                previous_element = child.create_element()
                element.append(previous_element)
                if child.id is not None:
                    previous_element.set(ID_KEY, str(child.id))

            elif isinstance(child, TextSegment):
                if previous_element is None:
                    element.text = append_text_in_element(
                        origin_text=element.text,
                        append_text=child.text,
                    )
                else:
                    previous_element.tail = append_text_in_element(
                        origin_text=previous_element.tail,
                        append_text=child.text,
                    )
        return element

    def validate(self, validated_element: Element):
        remain_expected_ids: set[int] = set()
        for child in self._child_inline_segments():
            if child.id is not None:
                remain_expected_ids.add(child.id)

        for _, child_element in iter_with_stack(validated_element):
            element_id = self._id_from_element(child_element)
            if element_id is None:
                continue
            if element_id in remain_expected_ids:
                remain_expected_ids.remove(element_id)
            else:
                yield InlineUnexpectedIDError(
                    id=element_id,
                    element=child_element,
                )

        if remain_expected_ids:
            yield InlineExceptedIDError(
                ids=sorted(remain_expected_ids),
            )

        yield from self._validate_tags(validated_element)

    def _child_inline_segments(self) -> Generator["InlineSegment", None, None]:
        for child in self._children:
            if isinstance(child, InlineSegment):
                yield child
                yield from child._child_inline_segments()  # pylint: disable=protected-access

    def _validate_tags(self, validated_element: Element):
        self_element = self._parent_stack[-1]
        tag2found_elements: dict[str, list[Element]] = {}

        for child_element in validated_element:
            ids = self._child_tag2ids.get(child_element.tag, None)
            if ids is None:
                found_elements = ensure_list(tag2found_elements, child_element.tag)
                found_elements.append(child_element)

            elif len(ids) > 0:
                id_str = child_element.get(ID_KEY, None)
                if id_str is None:
                    yield InlineLostIDError(
                        element=child_element,
                        stack=[self_element],
                    )

        for tag, found_elements in tag2found_elements.items():
            expected_count = self._child_tag2count.get(tag, 0)
            if len(found_elements) != expected_count:
                yield InlineWrongTagCountError(
                    expected_count=expected_count,
                    found_elements=found_elements,
                    stack=[self_element],
                )

        for child, child_element in self._match_children(validated_element):
            # pylint: disable=protected-access
            for error in child._validate_tags(child_element):
                error.stack.insert(0, self_element)
                yield error

    def _match_children(self, element: Element) -> Generator[tuple["InlineSegment", Element], None, None]:
        tag2elements = nest((c.tag, c) for c in element)
        tag2children = nest(
            (c.parent_stack[-1].tag, (i, c))
            for i, c in enumerate(c for c in self._children if isinstance(c, InlineSegment))
        )
        children_and_elements: list[tuple[int, InlineSegment, Element]] = []
        for tag, orders_and_children in tag2children.items():
            # 优先考虑 id 匹配，剩下的以自然顺序尽可能匹配
            ids = self._child_tag2ids.get(tag, [])
            matched_children_elements: list[Element | None] = [None] * len(orders_and_children)
            not_matched_elements: list[Element] = []

            for child_element in tag2elements.get(tag, []):
                id_order = -1
                child_id = self._id_from_element(child_element)
                if child_id is not None:
                    id_order = ids.index(child_id)
                if id_order == -1:
                    not_matched_elements.append(child_element)
                else:
                    matched_children_elements[id_order] = child_element

            not_matched_elements.reverse()
            for i in range(len(matched_children_elements)):
                if not not_matched_elements:
                    break
                matched_element = matched_children_elements[i]
                if matched_element is None:
                    matched_children_elements[i] = not_matched_elements.pop()

            for (order, child), child_element in zip(orders_and_children, matched_children_elements):
                if child_element is not None:
                    children_and_elements.append((order, child, child_element))

        for _, child, child_element in sorted(children_and_elements, key=lambda x: x[0]):
            yield child, child_element

    def _id_from_element(self, element: Element) -> int | None:
        id_str = element.get(ID_KEY, None)
        if id_str is None:
            return None
        try:
            return int(id_str)
        except ValueError:
            return None
