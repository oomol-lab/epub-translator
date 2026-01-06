from collections.abc import Generator, Iterable, Iterator
from dataclasses import dataclass
from xml.etree.ElementTree import Element

from ..utils import ensure_list, is_the_same, nest
from ..xml import ID_KEY, append_text_in_element, iter_with_stack, plain_text
from .common import FoundInvalidIDError, validate_id_in_element
from .text_segment import TextSegment
from .utils import IDGenerator, element_fingerprint, id_in_element


@dataclass
class InlineLostIDError:
    element: Element
    stack: list[Element]


@dataclass
class InlineUnexpectedIDError:
    id: int
    element: Element


@dataclass
class InlineExpectedIDsError:
    id2element: dict[int, Element]


@dataclass
class InlineWrongTagCountError:
    expected_count: int
    found_elements: list[Element]
    stack: list[Element]


InlineError = InlineLostIDError | InlineUnexpectedIDError | InlineExpectedIDsError | InlineWrongTagCountError


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
        inline_segment.id = id_generator.next_id()
        inline_segment.recreate_ids(id_generator)
    return inline_segment, next_text_segment


def search_inline_segments(text_segments: Iterable[TextSegment]) -> Generator["InlineSegment", None, None]:
    text_segments_iter = iter(text_segments)
    text_segment = next(text_segments_iter, None)
    while text_segment is not None:
        inline_segment, text_segment = _collect_next_inline_segment(
            first_text_segment=text_segment,
            text_segments_iter=text_segments_iter,
        )
        if inline_segment is not None:
            yield inline_segment


def _collect_next_inline_segment(
    first_text_segment: TextSegment,
    text_segments_iter: Iterator[TextSegment],
    depth: int | None = None,
) -> tuple["InlineSegment | None", TextSegment | None]:
    if depth is None:
        depth = first_text_segment.block_depth

    current_text_segment: TextSegment | None = first_text_segment
    children: list[TextSegment | InlineSegment] = []
    last_block_parent: Element | None = None

    while current_text_segment is not None:
        text_segment_depth = len(current_text_segment.parent_stack)
        if text_segment_depth < depth:
            break
        elif text_segment_depth == depth:
            if last_block_parent is not None and last_block_parent is not current_text_segment.block_parent:
                break
            children.append(current_text_segment)
            last_block_parent = current_text_segment.block_parent
            current_text_segment = next(text_segments_iter, None)
        else:
            if current_text_segment.block_depth > depth:
                break
            inline_text, current_text_segment = _collect_next_inline_segment(
                first_text_segment=current_text_segment,
                text_segments_iter=text_segments_iter,
                depth=depth + 1,
            )
            if inline_text is not None:
                children.append(inline_text)
            if current_text_segment is not None:
                reference_block_parent = (
                    last_block_parent if last_block_parent is not None else first_text_segment.block_parent
                )
                if reference_block_parent is not current_text_segment.block_parent:
                    break

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

        # 每一组 tag 都对应一个 ids 列表。
        # 若为空，说明该 tag 属性结构全同，没必要分配 id 以区分。
        # 若非空，则表示 tag 下每一个 element 都有 id 属性。
        # 注意，相同 tag 下的 element 要么全部有 id，要么全部都没有 id
        self._child_tag2ids: dict[str, list[int]] = {}
        self._child_tag2count: dict[str, int] = {}

        next_temp_id: int = 0
        terms = nest((child.parent.tag, child) for child in children if isinstance(child, InlineSegment))

        for _, child_terms in terms.items():
            if not is_the_same(  # 仅当 tag 彼此无法区分时才分配 id，以尽可能减少 id 的数量
                elements=(element_fingerprint(t.parent) for t in child_terms),
            ):
                for child in child_terms:
                    child.id = next_temp_id
                    next_temp_id += 1

    @property
    def head(self) -> TextSegment:
        first_child = self._children[0]
        if isinstance(first_child, TextSegment):
            return first_child
        else:
            return first_child.head

    @property
    def tail(self) -> TextSegment:
        last_child = self._children[-1]
        if isinstance(last_child, TextSegment):
            return last_child
        else:
            return last_child.tail

    @property
    def children(self) -> list["TextSegment | InlineSegment"]:
        return self._children

    @property
    def parent(self) -> Element:
        return self._parent_stack[-1]

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
                child_tag = child.parent.tag
                ids = ensure_list(self._child_tag2ids, child_tag)
                if child.id is not None:
                    child.id = id_generator.next_id()
                    ids.append(child.id)
                child.recreate_ids(id_generator)
                self._child_tag2count[child_tag] = self._child_tag2count.get(child_tag, 0) + 1

    def create_element(self) -> Element:
        element = Element(self.parent.tag)
        previous_element: Element | None = None
        for child in self._children:
            if isinstance(child, InlineSegment):
                previous_element = child.create_element()
                element.append(previous_element)

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
        if self.id is not None:
            element.set(ID_KEY, str(self.id))
        return element

    def validate(self, validated_element: Element) -> Generator[InlineError | FoundInvalidIDError, None, None]:
        remain_expected_elements: dict[int, Element] = {}
        for child in self._child_inline_segments():
            if child.id is not None:
                remain_expected_elements[child.id] = child.parent

        for _, child_element in iter_with_stack(validated_element):
            if child_element is validated_element:
                continue  # skip the root self

            element_id = id_in_element(child_element)
            if element_id is None:
                validated_id = validate_id_in_element(
                    element=child_element,
                    enable_no_id=True,
                )
                if isinstance(validated_id, FoundInvalidIDError):
                    yield validated_id
                continue

            remain_expected_element = remain_expected_elements.pop(element_id, None)
            if remain_expected_element is None:
                yield InlineUnexpectedIDError(
                    id=element_id,
                    element=child_element,
                )

        if remain_expected_elements:
            yield InlineExpectedIDsError(
                id2element=remain_expected_elements,
            )

        yield from self._validate_children_structure(validated_element)

    def _child_inline_segments(self) -> Generator["InlineSegment", None, None]:
        for child in self._children:
            if isinstance(child, InlineSegment):
                yield child
                yield from child._child_inline_segments()  # pylint: disable=protected-access

    def _validate_children_structure(self, validated_element: Element):
        tag2found_elements: dict[str, list[Element]] = {}

        for child_element in validated_element:
            ids = self._child_tag2ids.get(child_element.tag, None)
            if not ids:
                found_elements = ensure_list(tag2found_elements, child_element.tag)
                found_elements.append(child_element)
            else:
                id_str = child_element.get(ID_KEY, None)
                if id_str is None:
                    yield InlineLostIDError(
                        element=child_element,
                        stack=[self.parent],
                    )

        for tag, found_elements in tag2found_elements.items():
            expected_count = self._child_tag2count.get(tag, 0)
            if len(found_elements) != expected_count:
                yield InlineWrongTagCountError(
                    expected_count=expected_count,
                    found_elements=found_elements,
                    stack=[self.parent],
                )

        for child, child_element in self._match_children(validated_element):
            # pylint: disable=protected-access
            for error in child._validate_children_structure(child_element):
                error.stack.insert(0, self.parent)
                yield error

    # 即便 self.validate(...) 的错误没有排除干净，也要尽可能匹配一个质量较高（尽力而为）的版本
    def assign_attributes(self, template_element: Element) -> Element:
        assigned_element = Element(self.parent.tag, self.parent.attrib)
        if template_element.text and template_element.text.strip():
            assigned_element.text = append_text_in_element(
                origin_text=assigned_element.text,
                append_text=template_element.text,
            )

        matched_child_element_ids: set[int] = set()
        for child, child_element in self._match_children(template_element):
            child_assigned_element = child.assign_attributes(child_element)
            assigned_element.append(child_assigned_element)
            matched_child_element_ids.add(id(child_element))

        assigned_child_element_stack = list(assigned_element)
        assigned_child_element_stack.reverse()

        previous_assigned_child_element: Element | None = None
        for child_element in template_element:
            # 只关心 child_element 是否是分割点，不关心它真实对应。极端情况下可能乱序，只好大致对上就行
            child_text: str = ""
            if id(child_element) not in matched_child_element_ids:
                child_text = plain_text(child_element)
            elif assigned_child_element_stack:
                previous_assigned_child_element = assigned_child_element_stack.pop()
            if child_element.tail is not None:
                child_text += child_element.tail
            if not child_text.strip():
                continue
            if previous_assigned_child_element is None:
                assigned_element.text = append_text_in_element(
                    origin_text=assigned_element.text,
                    append_text=child_text,
                )
            else:
                previous_assigned_child_element.tail = append_text_in_element(
                    origin_text=previous_assigned_child_element.tail,
                    append_text=child_text,
                )
        return assigned_element

    def _match_children(self, element: Element) -> Generator[tuple["InlineSegment", Element], None, None]:
        tag2elements = nest((c.tag, c) for c in element)
        tag2children = nest(
            (c.parent.tag, (i, c)) for i, c in enumerate(c for c in self._children if isinstance(c, InlineSegment))
        )
        used_ids: set[int] = set()
        children_and_elements: list[tuple[int, InlineSegment, Element]] = []

        for tag, orders_and_children in tag2children.items():
            # 优先考虑 id 匹配，剩下的以自然顺序尽可能匹配
            ids = self._child_tag2ids.get(tag, [])
            matched_children_elements: list[Element | None] = [None] * len(orders_and_children)
            not_matched_elements: list[Element] = []

            for child_element in tag2elements.get(tag, []):
                id_order: int | None = None
                child_id = id_in_element(child_element)
                if child_id is not None and child_id not in used_ids:
                    used_ids.add(child_id)  # 一个 id 只能用一次，防止重复
                    try:
                        id_order = ids.index(child_id)
                    except ValueError:
                        pass
                if id_order is None:
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
