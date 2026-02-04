from xml.etree.ElementTree import Element

# HTML inline-level elements
# Reference: https://developer.mozilla.org/en-US/docs/Web/HTML/Inline_elements
# Reference: https://developer.mozilla.org/en-US/docs/Glossary/Inline-level_content
_HTML_INLINE_TAGS = frozenset(
    (
        # Inline text semantics
        "a",
        "abbr",
        "b",
        "bdi",
        "bdo",
        "br",
        "cite",
        "code",
        "data",
        "dfn",
        "em",
        "i",
        "kbd",
        "mark",
        "q",
        "rp",
        "rt",
        "ruby",
        "s",
        "samp",
        "small",
        "span",
        "strong",
        "sub",
        "sup",
        "time",
        "u",
        "var",
        "wbr",
        # Image and multimedia
        "img",
        "svg",
        "canvas",
        "audio",
        "video",
        "map",
        "area",
        # Form elements
        "input",
        "button",
        "select",
        "textarea",
        "label",
        "output",
        "progress",
        "meter",
        # Embedded content
        "iframe",
        "embed",
        "object",
        # Other inline elements
        "script",
        "del",
        "ins",
        "slot",
    )
)


def is_inline_element(element: Element) -> bool:
    if element.tag.lower() in _HTML_INLINE_TAGS:
        return True
    display = element.get("display", None)
    if display is not None and display.lower() == "inline":
        return True
    return False
