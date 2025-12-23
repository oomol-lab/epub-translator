from xml.etree.ElementTree import Element

from ..llm import LLM


class Filler:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm

    def fill(self, source_ele: Element, translated_text: str):
        pass
