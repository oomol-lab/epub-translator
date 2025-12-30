from collections.abc import Generator, Iterable
from dataclasses import dataclass
from xml.etree.ElementTree import Element

from resource_segmentation import Resource, Segment, split
from tiktoken import Encoding

from .fragmented import group_fragmented_elements
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
        for grouped_elements in group_fragmented_elements(
            encoding=self._encoding,
            elements=elements,
            group_max_tokens=self._max_group_tokens,
        ):
            for group in split(
                resources=self._expand_text_segments(grouped_elements),
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

    def _expand_text_segments(self, elements: Iterable[Element]):
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
                count=len(self._encoding.encode(segment.xml_text)),
                start_incision=start_incision,
                end_incision=incision1,
                payload=segment,
            )
            segment = next_segment
            start_incision = incision2

        yield Resource(
            count=len(self._encoding.encode(segment.xml_text)),
            start_incision=start_incision,
            end_incision=_BORDER_INCISION,
            payload=segment,
        )

    def _expand_text_segments_with_items(self, items: list[Resource[TextSegment] | Segment[TextSegment]]):
        for item in items:
            if isinstance(item, Resource):
                yield item.payload.clone()
            elif isinstance(item, Segment):
                for resource in item.resources:
                    yield resource.payload.clone()

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
            raw_xml_text = segment.xml_text
            tokens = self._encoding.encode(raw_xml_text)
            tokens_count = len(tokens)

            if tokens_count > remain_count:
                truncated_segment = self._truncate_text_segment(
                    segment=segment,
                    tokens=tokens,
                    raw_xml_text=raw_xml_text,
                    remain_head=remain_head,
                    remain_count=remain_count,
                )
                if truncated_segment is not None:
                    yield truncated_segment
                break

            yield segment
            remain_count -= tokens_count

    def _truncate_text_segment(
        self,
        segment: TextSegment,
        tokens: list[int],
        raw_xml_text: str,
        remain_head: bool,
        remain_count: int,
    ) -> TextSegment | None:
        # 典型的 xml_text: <tag id="99" data-origin-len="999">Some text</tag>
        # 如果切割点在前缀 XML 区，则整体舍弃
        # 如果切割点在后缀 XML 区，则整体保留
        # 只有刚好切割在正文区，才执行文本截断操作
        remain_text: str
        xml_text_head_length = raw_xml_text.find(segment.text)

        if remain_head:
            remain_xml_text = self._encoding.decode(tokens[:remain_count])  # remain_count cannot be 0 here
            if len(remain_xml_text) <= xml_text_head_length:
                return
            if len(remain_xml_text) >= xml_text_head_length + len(segment.text):
                return segment
            remain_text = remain_xml_text[xml_text_head_length:]
        else:
            xml_text_tail_length = len(raw_xml_text) - (xml_text_head_length + len(segment.text))
            remain_xml_text = self._encoding.decode(tokens[-remain_count:])
            if len(remain_xml_text) <= xml_text_tail_length:
                return
            if len(remain_xml_text) >= xml_text_tail_length + len(segment.text):
                return segment
            remain_text = remain_xml_text[: len(remain_xml_text) - xml_text_tail_length]

        if not remain_text.strip():
            return

        if remain_head:
            segment.text = f"{remain_text} {_ELLIPSIS}"
        else:
            segment.text = f"{_ELLIPSIS} {remain_text}"
        return segment
