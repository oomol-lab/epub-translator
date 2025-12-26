from xml.etree.ElementTree import Element

_MATH_TAG = "math"


def try_render_math_expression(element: Element) -> str | None:
    if element.tag != _MATH_TAG:
        return None


def _xml_to_latex(element: Element) -> str: ...
