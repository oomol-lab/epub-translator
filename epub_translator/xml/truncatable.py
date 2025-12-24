from typing import Self
from xml.etree.ElementTree import Element

from epub_translator.serial.segment import Segment


class TruncatableXML(Segment[Element]):
    text: str
    tokens: int
    payload: Element

    def __init__(self, payload: Element) -> None:
        self.payload = payload

    def truncate_after_head(self, remain_tokens: int) -> Self: ...
    def truncate_before_tail(self, remain_tokens: int) -> Self: ...
