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


def is_inline_tag(tag: str) -> bool:
    return tag.lower() in _HTML_INLINE_TAGS
