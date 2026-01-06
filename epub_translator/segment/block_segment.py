from collections.abc import Generator, Iterable
from dataclasses import dataclass
from typing import cast
from xml.etree.ElementTree import Element

from .common import FoundInvalidIDError, validate_id_in_element
from .inline_segment import InlineError, InlineSegment, collect_next_inline_segment
from .text_segment import TextSegment
from .utils import IDGenerator, id_in_element


@dataclass
class BlockSubmitter:
    id: int
    origin_text_segments: list[TextSegment]
    submitted_element: Element


@dataclass
class BlockWrongTagError:
    block: tuple[int, Element] | None  # (block_id, block_element) | None 表示根元素
    expected_tag: str
    instead_tag: str


@dataclass
class BlockUnexpectedIDError:
    id: int
    element: Element


@dataclass
class BlockExpectedIDsError:
    id2element: dict[int, Element]


@dataclass
class BlockContentError:
    id: int
    element: Element
    errors: list[InlineError | FoundInvalidIDError]


BlockError = BlockWrongTagError | BlockUnexpectedIDError | BlockExpectedIDsError | BlockContentError


class BlockSegment:
    # TODO: 当前版本忽略了嵌入文字的 Block 概念，这是书籍中可能出现的一种情况，虽然不多见。
    #       例如，作为非叶子的块元素，它的子块元素之间会夹杂文本，当前 collect_next_inline_segment 会忽略这些文字：
    #       <div>
    #         Some text before.
    #         <!-- 只有下一行作为叶子节点的块元素内的文字会被处理 -->
    #         <div>Paragraph 1.</div>
    #         Some text in between.
    #       </div>
    def __init__(self, root_tag: str, text_segments: Iterable[TextSegment]) -> None:
        self._root_tag: str = root_tag
        self._inline_segments: list[InlineSegment] = list(_transform_to_inline_segments(text_segments))
        self._id2inline_segment: dict[int, InlineSegment] = dict((cast(int, s.id), s) for s in self._inline_segments)

    def __iter__(self) -> Generator[InlineSegment, None, None]:
        yield from self._inline_segments

    def create_element(self) -> Element:
        root_element = Element(self._root_tag)
        for inline_segment in self._inline_segments:
            root_element.append(inline_segment.create_element())
        return root_element

    def validate(self, validated_element: Element) -> Generator[BlockError | FoundInvalidIDError, None, None]:
        if validated_element.tag != self._root_tag:
            yield BlockWrongTagError(
                block=None,
                expected_tag=self._root_tag,
                instead_tag=validated_element.tag,
            )

        remain_expected_elements: dict[int, Element] = dict(
            (id, inline_segment.parent) for id, inline_segment in self._id2inline_segment.items()
        )
        for child_validated_element in validated_element:
            element_id = validate_id_in_element(child_validated_element)
            if isinstance(element_id, FoundInvalidIDError):
                yield element_id
            else:
                inline_segment = self._id2inline_segment.get(element_id, None)
                if inline_segment is None:
                    yield BlockUnexpectedIDError(
                        id=element_id,
                        element=child_validated_element,
                    )
                else:
                    if inline_segment.parent.tag != child_validated_element.tag:
                        yield BlockWrongTagError(
                            block=(cast(int, inline_segment.id), inline_segment.parent),
                            expected_tag=inline_segment.parent.tag,
                            instead_tag=child_validated_element.tag,
                        )

                    remain_expected_elements.pop(element_id, None)
                    inline_errors = list(inline_segment.validate(child_validated_element))

                    if inline_errors:
                        yield BlockContentError(
                            id=element_id,
                            element=child_validated_element,
                            errors=inline_errors,
                        )

        if remain_expected_elements:
            yield BlockExpectedIDsError(id2element=remain_expected_elements)

    def submit(self, target: Element) -> Generator[BlockSubmitter, None, None]:
        for child_element in target:
            element_id = id_in_element(child_element)
            if element_id is None:
                continue
            inline_segment = self._id2inline_segment.get(element_id, None)
            if inline_segment is None:
                continue
            inline_segment_id = inline_segment.id
            assert inline_segment_id is not None
            yield BlockSubmitter(
                id=inline_segment_id,
                origin_text_segments=list(inline_segment),
                submitted_element=inline_segment.assign_attributes(child_element),
            )


def _transform_to_inline_segments(text_segments: Iterable[TextSegment]) -> Generator[InlineSegment, None, None]:
    id_generator = IDGenerator()
    text_segments_iter = iter(text_segments)
    text_segment = next(text_segments_iter, None)
    while text_segment is not None:
        inline_segment, text_segment = collect_next_inline_segment(
            id_generator=id_generator,
            first_text_segment=text_segment,
            text_segments_iter=text_segments_iter,
        )
        if inline_segment is not None:
            yield inline_segment
