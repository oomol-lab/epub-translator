from collections.abc import Generator, Iterable
from xml.etree.ElementTree import Element

from resource_segmentation import Group, Resource, Segment, split
from tiktoken import Encoding

from .text_segment import TextSegment, combine_text_segments, incision_between, search_text_segments

_BORDER_INCISION = 0
_ELLIPSIS = "..."


class Translator2:
    def __init__(self, encoding: Encoding, max_group_tokens: int) -> None:
        self._encoding: Encoding = encoding
        self._max_group_tokens: int = max_group_tokens

    def translate(self, element: Element):
        for group in split(
            resources=self._expand_truncatable(element),
            max_segment_count=self._max_group_tokens,
            border_incision=_BORDER_INCISION,
        ):
            combined_generator = combine_text_segments(
                segments=self._expand_text_segments_with_group(group),
            )
            combined_element = next(combined_generator, None)
            if combined_element is None:
                continue
            # TODO: 翻译整个片段，然后将它们拼起来

    def _expand_truncatable(self, element: Element) -> Generator[Resource[TextSegment], None, None]:
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
                yield segment
                remain_count -= count
                continue

            remain_count -= count
            remain_text_tokens = segment.text
            if remain_head:
                remain_text_tokens = tokens[:remain_count]
            else:
                remain_text_tokens = tokens[-remain_count:]

            remain_text = self._encoding.decode(remain_text_tokens)
            if not remain_text.strip():
                continue

            if remain_head:
                remain_text = f"{remain_text} {_ELLIPSIS}"
            else:
                remain_text = f"{_ELLIPSIS} {remain_text}"

            yield TextSegment(
                text=remain_text,
                element=segment.element,
                index=segment.index,
                parent_stack=segment.parent_stack,
                block_depth=segment.block_depth,
            )

    def _unwrap_parents(self, element: Element) -> Element:
        while True:
            if len(element) != 1:
                break
            child = element[0]
            if not element.text:
                break
            if not child.tail:
                break
            element = child
            element.tail = None
        return element
