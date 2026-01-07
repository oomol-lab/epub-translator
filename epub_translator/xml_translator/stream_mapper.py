from collections.abc import Callable, Generator, Iterable, Iterator
from xml.etree.ElementTree import Element

from resource_segmentation import Resource, Segment, split
from tiktoken import Encoding

from ..segment import InlineSegment, TextSegment, search_inline_segments, search_text_segments

_PAGE_INCISION = 0
_BLOCK_INCISION = 1

_ELLIPSIS = "..."


InlineSegmentMapping = tuple[InlineSegment, list[TextSegment]]
InlineSegmentGroupMap = Callable[[list[InlineSegment]], list[InlineSegmentMapping | None]]


class XMLStreamMapper:
    def __init__(self, encoding: Encoding, max_group_tokens: int) -> None:
        self._encoding: Encoding = encoding
        self._max_group_tokens: int = max_group_tokens

    def map_stream(
        self,
        elements: Iterator[Element],
        map: InlineSegmentGroupMap,
    ) -> Generator[tuple[Element, list[InlineSegmentMapping]], None, None]:
        current_element: Element | None = None
        mapping_buffer: list[InlineSegmentMapping] = []

        for head, body, tail in self._split_into_groups(elements):
            target_body = map(head + body + tail)[len(head) : len(head) + len(body)]
            for origin, target in zip(body, target_body):
                origin_element = origin.head.root
                if current_element is None:
                    current_element = origin_element

                if id(current_element) != id(origin_element):
                    yield current_element, mapping_buffer
                    current_element = origin_element
                    mapping_buffer = []
                if target:
                    mapping_buffer.append(target)

        if current_element is not None:
            yield current_element, mapping_buffer

    def _split_into_groups(self, elements: Iterator[Element]):
        for group in split(
            resources=self._expand_to_resources(elements),
            max_segment_count=self._max_group_tokens,
            border_incision=_PAGE_INCISION,
        ):
            head = list(
                self._truncate_inline_segments(
                    inline_segments=self._expand_inline_segments(group.head),
                    remain_head=False,
                    remain_count=group.head_remain_count,
                )
            )
            body = list(self._expand_inline_segments(group.body))
            tail = list(
                self._truncate_inline_segments(
                    inline_segments=self._expand_inline_segments(group.tail),
                    remain_head=True,
                    remain_count=group.tail_remain_count,
                )
            )
            yield head, body, tail

    def _expand_to_resources(self, elements: Iterator[Element]) -> Generator[Resource[InlineSegment], None, None]:
        def expand(elements: Iterator[Element]):
            for element in elements:
                yield from search_inline_segments(
                    text_segments=search_text_segments(element),
                )

        inline_segment_generator = expand(elements)
        start_incision = _PAGE_INCISION
        inline_segment = next(inline_segment_generator, None)
        if inline_segment is None:
            return

        while True:
            next_inline_segment = next(inline_segment_generator, None)
            if next_inline_segment is None:
                break

            if next_inline_segment.head.root is inline_segment.tail.root:
                end_incision = _BLOCK_INCISION
            else:
                end_incision = _PAGE_INCISION

            yield Resource(
                count=sum(len(self._encoding.encode(t.xml_text)) for t in inline_segment),
                start_incision=start_incision,
                end_incision=end_incision,
                payload=inline_segment,
            )
            inline_segment = next_inline_segment
            start_incision = end_incision

        yield Resource(
            count=sum(len(self._encoding.encode(t.xml_text)) for t in inline_segment),
            start_incision=start_incision,
            end_incision=_PAGE_INCISION,
            payload=inline_segment,
        )

    def _truncate_inline_segments(self, inline_segments: Iterable[InlineSegment], remain_head: bool, remain_count: int):
        def clone_and_expand(segments: Iterable[InlineSegment]):
            for segment in segments:
                for child_segment in segment:
                    yield child_segment.clone()  # 切割对应的 head 和 tail 会与其他 group 重叠，复制避免互相影响

        truncated_text_segments = self._truncate_text_segments(
            text_segments=clone_and_expand(inline_segments),
            remain_head=remain_head,
            remain_count=remain_count,
        )
        yield from search_inline_segments(truncated_text_segments)

    def _expand_inline_segments(self, items: list[Resource[InlineSegment] | Segment[InlineSegment]]):
        for item in items:
            if isinstance(item, Resource):
                yield item.payload
            elif isinstance(item, Segment):
                for resource in item.resources:
                    yield resource.payload

    def _truncate_text_segments(self, text_segments: Iterable[TextSegment], remain_head: bool, remain_count: int):
        if remain_head:
            yield from self._filter_and_remain_segments(
                segments=text_segments,
                remain_head=remain_head,
                remain_count=remain_count,
            )
        else:
            yield from reversed(
                list(
                    self._filter_and_remain_segments(
                        segments=reversed(list(text_segments)),
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
                return None
            if len(remain_xml_text) >= xml_text_head_length + len(segment.text):
                return segment
            remain_text = remain_xml_text[xml_text_head_length:]
        else:
            xml_text_tail_length = len(raw_xml_text) - (xml_text_head_length + len(segment.text))
            remain_xml_text = self._encoding.decode(tokens[-remain_count:])
            if len(remain_xml_text) <= xml_text_tail_length:
                return None
            if len(remain_xml_text) >= xml_text_tail_length + len(segment.text):
                return segment
            remain_text = remain_xml_text[: len(remain_xml_text) - xml_text_tail_length]

        if not remain_text.strip():
            return None

        if remain_head:
            segment.text = f"{remain_text} {_ELLIPSIS}"
        else:
            segment.text = f"{_ELLIPSIS} {remain_text}"
        return segment
