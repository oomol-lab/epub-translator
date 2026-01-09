from collections.abc import Callable, Generator, Iterable, Iterator
from xml.etree.ElementTree import Element

from resource_segmentation import Group, Resource, Segment, split
from tiktoken import Encoding

from ..segment import InlineSegment, TextSegment, search_inline_segments, search_text_segments
from .callbacks import Callbacks

_PAGE_INCISION = 0
_BLOCK_INCISION = 1

_ELLIPSIS = "..."


InlineSegmentMapping = tuple[Element, list[TextSegment]]
InlineSegmentGroupMap = Callable[[list[InlineSegment]], list[InlineSegmentMapping | None]]


class XMLStreamMapper:
    def __init__(self, encoding: Encoding, max_group_tokens: int) -> None:
        self._encoding: Encoding = encoding
        self._max_group_tokens: int = max_group_tokens

    def map_stream(
        self,
        elements: Iterator[Element],
        callbacks: Callbacks,
        map: InlineSegmentGroupMap,
    ) -> Generator[tuple[Element, list[InlineSegmentMapping]], None, None]:
        current_element: Element | None = None
        mapping_buffer: list[InlineSegmentMapping] = []

        for group in self._split_into_serial_groups(elements, callbacks):
            head, body, tail = self._truncate_and_transform_group(group)
            target_body = map(head + body + tail)[len(head) : len(head) + len(body)]
            for origin, target in zip(body, target_body, strict=False):
                origin_element = origin.head.root
                if current_element is None:
                    current_element = origin_element

                if id(current_element) != id(origin_element):
                    yield current_element, mapping_buffer
                    current_element = origin_element
                    mapping_buffer = []

                if target:
                    block_element, text_segments = target
                    block_element = callbacks.interrupt_block_element(block_element)
                    text_segments = list(callbacks.interrupt_translated_text_segments(text_segments))
                    if text_segments:
                        mapping_buffer.append((block_element, text_segments))

        if current_element is not None:
            yield current_element, mapping_buffer

    def _split_into_serial_groups(self, elements: Iterable[Element], callbacks: Callbacks):
        def generate():
            for element in elements:
                yield from split(
                    max_segment_count=self._max_group_tokens,
                    border_incision=_PAGE_INCISION,
                    resources=self._expand_to_resources(element, callbacks),
                )

        generator = generate()
        group = next(generator, None)
        if group is None:
            return

        # head + body * N (without tail)
        sum_count = group.head_remain_count + sum(x.count for x in self._expand_resource_segments(group.body))

        while True:
            next_group = next(generator, None)
            if next_group is None:
                break

            next_sum_body_count = sum(x.count for x in self._expand_resource_segments(next_group.body))
            next_sum_count = sum_count + next_sum_body_count

            if next_sum_count + next_group.tail_remain_count > self._max_group_tokens:
                yield group
                group = next_group
                sum_count = group.head_remain_count + next_sum_body_count
            else:
                group.body.extend(next_group.body)
                group.tail = next_group.tail
                group.tail_remain_count = next_group.tail_remain_count
                sum_count = next_sum_count

        yield group

    def _truncate_and_transform_group(self, group: Group[InlineSegment]):
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
        return head, body, tail

    def _expand_to_resources(self, element: Element, callbacks: Callbacks):
        def expand(element: Element):
            text_segments = search_text_segments(element)
            text_segments = callbacks.interrupt_source_text_segments(text_segments)
            yield from search_inline_segments(text_segments)

        inline_segment_generator = expand(element)
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
        for resource in self._expand_resource_segments(items):
            yield resource.payload

    def _expand_resource_segments(self, items: list[Resource[InlineSegment] | Segment[InlineSegment]]):
        for item in items:
            if isinstance(item, Resource):
                yield item
            elif isinstance(item, Segment):
                yield from item.resources

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
