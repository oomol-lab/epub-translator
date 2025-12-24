from xml.etree.ElementTree import Element


class Translator:
    def translate(self, text: str, element: Element) -> Element: ...
