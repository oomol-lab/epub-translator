from collections.abc import Generator, Iterable
from dataclasses import dataclass
from xml.etree.ElementTree import Element

from resource_segmentation import Group, Resource, Segment, split
from tiktoken import Encoding

from .text_segment import TextSegment, incision_between, search_text_segments

_BORDER_INCISION = 0
_ELLIPSIS = "..."


@dataclass
class XMLGroup:
    head: list[TextSegment]
    body: list[TextSegment]
    tail: list[TextSegment]

    def __iter__(self) -> Generator[TextSegment, None, None]:
        yield from self.head
        yield from self.body
        yield from self.tail


class XMLGroupContext:
    def __init__(self, encoding: Encoding, max_group_tokens: int) -> None:
        self._encoding: Encoding = encoding
        self._max_group_tokens: int = max_group_tokens

    def split_groups(self, elements: Iterable[Element]) -> Generator[XMLGroup, None, None]:
        # FIXME: 会把内存撑爆，将连续小片段 chapters 合并，但对于大 chapter 应该一对一 split
        for group in split(
            resources=self._expend_text_segments(elements),
            max_segment_count=self._max_group_tokens,
            border_incision=_BORDER_INCISION,
        ):
            yield XMLGroup(
                head=list(
                    self._truncate_text_segments(
                        segments=self._expand_text_segments_with_items(group.head),
                        remain_head=False,
                        remain_count=group.head_remain_count,
                    )
                ),
                body=list(self._expand_text_segments_with_items(group.body)),
                tail=list(
                    self._truncate_text_segments(
                        segments=self._expand_text_segments_with_items(group.tail),
                        remain_head=True,
                        remain_count=group.tail_remain_count,
                    )
                ),
            )

    def _expend_text_segments(self, elements: Iterable[Element]):
        for element in elements:
            yield from self._expand_text_segments_with_element(element)

    def _expand_text_segments_with_element(self, element: Element) -> Generator[Resource[TextSegment], None, None]:
        generator = search_text_segments(element)
        segment = next(generator, None)
        start_incision = _BORDER_INCISION
        if segment is None:
            return

        while True:
            next_segment = next(generator, None)
            if next_segment is None:
                break
            incision1, incision2 = incision_between(
                segment1=segment,
                segment2=next_segment,
            )
            yield Resource(
                count=len(self._encoding.encode(segment.text)),
                start_incision=start_incision,
                end_incision=incision1,
                payload=segment,
            )
            segment = next_segment
            start_incision = incision2

        yield Resource(
            count=len(self._encoding.encode(segment.text)),
            start_incision=start_incision,
            end_incision=_BORDER_INCISION,
            payload=segment,
        )

    def _expand_text_segments_with_group(self, group: Group[TextSegment]):
        yield from self._truncate_text_segments(
            segments=self._expand_text_segments_with_items(group.head),
            remain_head=False,
            remain_count=group.head_remain_count,
        )
        yield from self._expand_text_segments_with_items(group.body)
        yield from self._truncate_text_segments(
            segments=self._expand_text_segments_with_items(group.tail),
            remain_head=True,
            remain_count=group.tail_remain_count,
        )

    def _expand_text_segments_with_items(self, items: list[Resource[TextSegment] | Segment[TextSegment]]):
        for item in items:
            if isinstance(item, Resource):
                yield item.payload
            elif isinstance(item, Segment):
                for resource in item.resources:
                    yield resource.payload

    def _truncate_text_segments(self, segments: Iterable[TextSegment], remain_head: bool, remain_count: int):
        if remain_head:
            yield from self._filter_and_remain_segments(
                segments=segments,
                remain_head=remain_head,
                remain_count=remain_count,
            )
        else:
            yield from reversed(
                list(
                    self._filter_and_remain_segments(
                        segments=reversed(list(segments)),
                        remain_head=remain_head,
                        remain_count=remain_count,
                    )
                )
            )

    def _filter_and_remain_segments(self, segments: Iterable[TextSegment], remain_head: bool, remain_count: int):
        for segment in segments:
            if remain_count <= 0:
                break
            tokens = self._encoding.encode(segment.text)
            count = len(tokens)
            if count <= remain_count:
                yield TextSegment(
                    text=segment.text,
                    index=segment.index,
                    parent_stack=segment.parent_stack,
                    block_depth=segment.block_depth,
                )
                remain_count -= count
                continue

            remain_count = 0
            remain_text = self._encoding.decode(
                # remain_count cannot be 0 here
                tokens=tokens[:remain_count] if remain_head else tokens[-remain_count:],
            )
            if remain_text.strip():
                yield TextSegment(
                    text=f"{remain_text} {_ELLIPSIS}" if remain_head else f"{_ELLIPSIS} {remain_text}",
                    index=segment.index,
                    parent_stack=segment.parent_stack,
                    block_depth=segment.block_depth,
                )
            break
