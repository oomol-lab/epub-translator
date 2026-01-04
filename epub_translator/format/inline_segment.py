from collections.abc import Iterator
from xml.etree.ElementTree import Element

from ..utils import is_the_same
from ..xml import append_text_in_element
from .text_segment import TextSegment
from .utils import IDGenerator, element_fingerprint


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
        inline_segment.reset_ids(id_generator)
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
        self._children: list[TextSegment | InlineSegment] = children
        self._parent_stack: list[Element] = children[0].parent_stack[:depth]
        self._ids_store: dict[int, int] = {}  # id(child) -> global id

        next_temp_id: int = 0
        terms: dict[str, list[TextSegment | InlineSegment]] = {}
        for child in children:
            parent = child.parent_stack[-1]
            child_terms = terms.get(parent.tag, None)
            if child_terms is None:
                child_terms = []
                terms[parent.tag] = child_terms
            child_terms.append(child)

        for _, child_terms in terms.items():
            if not is_the_same(  # 仅当 tag 彼此无法区分时才分配 id，以尽可能减少 id 的数量
                elements=(element_fingerprint(t.parent_stack[-1]) for t in child_terms),
            ):
                for child in child_terms:
                    self._ids_store[id(child)] = next_temp_id
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

    def reset_ids(self, id_generator: IDGenerator) -> None:
        for child in self._children:
            if isinstance(child, InlineSegment):
                child.reset_ids(id_generator)
            else:
                child_id = id(child)
                if child_id in self._ids_store:
                    self._ids_store[child_id] = id_generator.next_id()

    def create_element(self) -> Element:
        element = Element(self.parent_stack[-1].tag)
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
        return element
