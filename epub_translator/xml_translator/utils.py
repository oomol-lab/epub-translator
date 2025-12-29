from ..utils import normalize_whitespace


def normalize_text_in_element(text: str | None) -> str | None:
    if text is None:
        return None
    text = normalize_whitespace(text)
    if not text.strip():
        return None
    return text
