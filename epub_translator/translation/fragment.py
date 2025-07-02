import re

from xml.etree.ElementTree import Element
from ..llm import LLM


_SPACE = re.compile(r"\s+")

def translate_chunk(llm: LLM, fragments: list[str]):
  request_element = Element("request")
  for i, fragment in enumerate(fragments):
    fragment_element = Element("fragment", attrib={
      "id": str(i + 1),
    })
    fragment_element.text = _SPACE.sub(" ", fragment.strip())
    request_element.append(fragment_element)

  resp_element = llm.request_xml(
    template_name="translate",
    user_data=request_element,
    params={
      "target_language": "英语",
    },
  )
  translated_fragments = [""] * len(fragments)
  for fragment_element in resp_element:
    if fragment_element.text is None:
      continue
    id = fragment_element.get("id", None)
    if id is None:
      continue
    index = int(id) - 1
    translated_fragments[index] = fragment_element.text.strip()

  return translated_fragments