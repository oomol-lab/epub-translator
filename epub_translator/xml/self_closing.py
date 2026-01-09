import re

# Some non-standard EPUB generators use HTML-style tags without self-closing syntax
# We need to convert them to XML-compatible format before parsing
# These are HTML5 void elements that must be self-closing in XHTML
_VOID_TAGS = (
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
)


def self_close_void_elements(xml_content: str) -> str:
    """
    Convert void HTML elements to self-closing format for XML parsing.

    This function handles non-standard HTML where void elements are not self-closed.
    For illegal cases like <meta>content</meta>, the content is removed.

    Args:
        xml_content: HTML/XHTML content string

    Returns:
        Content with void elements in self-closing format

    Example:
        <meta charset="utf-8"> → <meta charset="utf-8" />
        <br> → <br />
        <meta>illegal</meta> → <meta />
    """
    for tag in _VOID_TAGS:
        xml_content = _fix_void_element(xml_content, tag)
    return xml_content


def _fix_void_element(content: str, tag_name: str) -> str:
    """
    Fix a specific void element in the content.

    Strategy:
    1. Find <tag ...> (not already self-closed)
    2. Check if there's a matching </tag>
    3. If yes, remove everything between them and make it self-closing
    4. If no, just make the opening tag self-closing
    """
    result = []
    pos = 0

    while pos < len(content):
        # Find next occurrence of opening tag
        tag_start = content.find(f"<{tag_name}", pos)
        if tag_start == -1:
            # No more tags, append rest of content
            result.append(content[pos:])
            break

        # Verify it's a complete tag match (not a prefix like <br matching <brain>)
        # The character after tag_name must be >, /, or whitespace
        check_pos = tag_start + len(f"<{tag_name}")
        if check_pos < len(content):
            next_char = content[check_pos]
            if next_char not in (">", "/", " ", "\t", "\n", "\r"):
                # Not a valid tag boundary, skip this match
                result.append(content[pos:check_pos])
                pos = check_pos
                continue

        # Append content before this tag
        result.append(content[pos:tag_start])

        # Find the end of the opening tag (first > after tag start)
        # Need to handle quotes: ignore > inside quoted strings
        tag_end = _find_tag_end(content, tag_start)
        if tag_end == -1:
            # Malformed, just append rest and break
            result.append(content[tag_start:])
            break

        opening_tag = content[tag_start : tag_end + 1]

        # Check if already self-closed
        if opening_tag.rstrip().endswith("/>"):
            # Already self-closed, keep as is
            result.append(opening_tag)
            pos = tag_end + 1
            continue

        # Check if it ends with >
        if not opening_tag.endswith(">"):
            # Malformed, keep as is
            result.append(opening_tag)
            pos = tag_end + 1
            continue

        # Look for closing tag
        closing_tag = f"</{tag_name}>"
        closing_pos = content.find(closing_tag, tag_end + 1)

        if closing_pos != -1:
            # Found closing tag, remove content between and make self-closing
            # Convert: <tag attrs>content</tag> → <tag attrs />
            attrs_part = opening_tag[len(f"<{tag_name}") : -1].rstrip()
            if attrs_part:
                result.append(f"<{tag_name}{attrs_part} />")
            else:
                result.append(f"<{tag_name} />")
            pos = closing_pos + len(closing_tag)
        else:
            # No closing tag, just make opening tag self-closing
            attrs_part = opening_tag[len(f"<{tag_name}") : -1].rstrip()
            if attrs_part:
                result.append(f"<{tag_name}{attrs_part} />")
            else:
                result.append(f"<{tag_name} />")
            pos = tag_end + 1

    return "".join(result)


def _find_tag_end(content: str, start_pos: int) -> int:
    """
    Find the end of an HTML tag (the position of >).

    Handles quotes: ignores > inside quoted attribute values.
    """
    pos = start_pos
    in_quote = None  # None, '"', or "'"

    while pos < len(content):
        char = content[pos]

        if in_quote:
            # Inside a quote, look for closing quote
            if char == in_quote:
                # Check if escaped
                if pos > 0 and content[pos - 1] == "\\":
                    # Escaped quote, continue
                    pos += 1
                    continue
                else:
                    # Closing quote
                    in_quote = None
        else:
            # Not in quote
            if char in ('"', "'"):
                in_quote = char
            elif char == ">":
                return pos

        pos += 1

    return -1  # Not found


# For saving: match self-closing tags like <br /> or <br/>
# Capture tag name and everything between tag name and />
_VOID_TAG_CLOSE_PATTERN = re.compile(r"<(" + "|".join(_VOID_TAGS) + r")([^>]*?)\s*/>")


def unclose_void_elements(xml_content: str) -> str:
    """
    Convert void elements from self-closing to unclosed format for HTML compatibility.

    Transforms self-closed void elements like <br /> back to <br> for
    compatibility with HTML parsers that don't support XHTML syntax.
    Used only for text/html media type files.

    Args:
        xml_content: HTML/XHTML content string

    Returns:
        Content with void elements in unclosed format

    Example:
        <meta charset="utf-8" /> → <meta charset="utf-8">
        <br /> → <br>
        <img src="test.png" /> → <img src="test.png">
    """

    def replacer(m):
        tag_name = m.group(1)
        attrs = m.group(2).rstrip()  # Remove trailing whitespace
        if attrs:
            return f"<{tag_name}{attrs}>"
        else:
            return f"<{tag_name}>"

    return re.sub(pattern=_VOID_TAG_CLOSE_PATTERN, repl=replacer, string=xml_content)
