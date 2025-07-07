import re


_EMPTY_LINE = re.compile(r"^\s*$")
_SPACE = re.compile(r"\s+")

def is_empty(text: str) -> bool:
  return bool(_EMPTY_LINE.match(text))

def clean_spaces(text: str) -> str:
  return _SPACE.sub(" ", text.strip())