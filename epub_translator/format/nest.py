from collections.abc import Iterable
from xml.etree.ElementTree import Element

from .text_segment import TextSegment


class NestXML:
    def __init__(self, text_segments: Iterable[TextSegment]) -> None:
        last_block_parent: Element | None = None
        text_segments_buffer: list[TextSegment] = []
        for text_segment in text_segments:
            if last_block_parent is None:
                last_block_parent = text_segment.block_parent
                text_segments_buffer.append(text_segment)
            elif id(last_block_parent) == id(text_segment.block_parent):
                text_segments_buffer.append(text_segment)
            else:
                pass


class InlineXML:
    def __init__(self) -> None:
        pass
