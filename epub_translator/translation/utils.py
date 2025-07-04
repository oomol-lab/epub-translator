import re


_SPACE = re.compile(r"\s+")

def clean_spaces(text: str) -> str:
  return _SPACE.sub(" ", text.strip())