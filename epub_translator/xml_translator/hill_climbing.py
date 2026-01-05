from collections.abc import Iterable
from xml.etree.ElementTree import Element

from tiktoken import Encoding

from ..segment import BlockSegment, TextSegment
from ..xml import plain_text
from .common import DATA_ORIGIN_LEN_KEY


# 以爬山算法，将 LLM 中提交的内容中挑选出完成度更高的部分。
# 它通过拒绝每个子部分的相对低完成度提交，锁定每个子部分只能往更高完成度的方向移动
class HillClimbing:
    def __init__(
        self,
        encoding: Encoding,
        request_tag: str,
        text_segments: Iterable[TextSegment],
    ) -> None:
        self._encoding: Encoding = encoding
        self._block_segment: BlockSegment = BlockSegment(
            root_tag=request_tag,
            text_segments=text_segments,
        )

    def request_element(self) -> Element:
        element = self._block_segment.create_element()
        for child_element in element:
            text = plain_text(child_element)
            tokens = self._encoding.encode(text)
            child_element.set(DATA_ORIGIN_LEN_KEY, str(len(tokens)))
        return element

    def submit(self, element: Element):
        for _ in self._block_segment.validate(element):
            pass
