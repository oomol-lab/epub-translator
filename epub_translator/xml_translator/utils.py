from xml.etree.ElementTree import Element

from ..utils import normalize_whitespace
from .const import DATA_ORIGIN_LEN_KEY, ID_KEY


def normalize_text_in_element(text: str | None) -> str | None:
    if text is None:
        return None
    text = normalize_whitespace(text)
    if not text.strip():
        return None
    return text


def expand_left_element_texts(element: Element):
    yield "<"
    yield element.tag
    yield " "
    yield ID_KEY
    yield '="99" '
    yield DATA_ORIGIN_LEN_KEY
    yield '="999">'


def expand_right_element_texts(element: Element):
    yield "</"
    yield element.tag
    yield ">"
