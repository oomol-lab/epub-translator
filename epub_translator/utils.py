import re

_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_whitespace(text: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", text)
