from typing import Self
from xml.etree.ElementTree import Element

from epub_translator.serial.segment import Segment


class TruncatableXML(Segment[Element]):
    _payload: Element

    def __init__(self, payload: Element) -> None:
        self._payload = payload

    @property
    def text(self) -> str: ...

    @property
    def tokens(self) -> int: ...

    @property
    def payload(self) -> Element:
        return self._payload

    def truncate_after_head(self, remain_tokens: int) -> Self: ...
    def truncate_before_tail(self, remain_tokens: int) -> Self: ...
