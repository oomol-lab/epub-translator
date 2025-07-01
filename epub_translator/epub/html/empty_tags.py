import re

# HTML 规定了一系列自闭标签，这些标签需要改成非自闭的，因为 EPub 格式不支持
# https://www.tutorialspoint.com/which-html-tags-are-self-closing
_EMPTY_TAGS = (
  "br",
  "hr",
  "input",
  "col",
  "base",
  "meta",
  "area",
)

_EMPTY_TAG_PATTERN = re.compile(
  r"<(" + "|".join(_EMPTY_TAGS) + r")(\s[^>]*?)\s*/?>"
)

def to_html(content: str) -> str:
  return re.sub(_EMPTY_TAG_PATTERN, lambda m: f"<{m.group(1)}{m.group(2)}>", content)

def to_xml(content: str) -> str:
  return re.sub(_EMPTY_TAG_PATTERN, lambda m: f"<{m.group(1)}{m.group(2)} />", content)