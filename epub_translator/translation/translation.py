import re

from typing import Iterable, Generator
from pathlib import Path
from xml.etree.ElementTree import Element

from ..llm import LLM
from .types import Fragment
from .store import Store
from .splitter import split_into_chunks
from .chunk import match_fragments


def translate(
      llm: LLM,
      fragments: Iterable[Fragment],
      cache_path: Path | None,
      max_chunk_tokens_count: int,
    )-> Generator[str, None, None]:

  store = Store(cache_path) if cache_path else None
  chunk_ranges = list(split_into_chunks(
    llm=llm,
    fragments_iter=iter(fragments),
    max_chunk_tokens_count=max_chunk_tokens_count,
  ))
  for chunk in match_fragments(
    llm=llm,
    chunk_ranges_iter=iter(chunk_ranges),
    fragments_iter=iter(fragments),
  ):
    translated_texts: list[str] | None = None
    if store is not None:
      translated_texts = store.get(chunk.hash)

    if translated_texts is None:
      translated_texts = _translate_texts(
        llm=llm,
        texts=chunk.head + chunk.body + chunk.tail,
      )
    if store is not None:
      store.put(chunk.hash, translated_texts)

    head_length = len(chunk.head)
    yield from translated_texts[head_length:head_length + len(chunk.body)]

_SPACE = re.compile(r"\s+")

def _translate_texts(llm: LLM, texts: list[str]):
  request_element = Element("request")
  for i, fragment in enumerate(texts):
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
  translated_fragments = [""] * len(texts)
  for fragment_element in resp_element:
    if fragment_element.text is None:
      continue
    id = fragment_element.get("id", None)
    if id is None:
      continue
    index = int(id) - 1
    translated_fragments[index] = fragment_element.text.strip()

  return translated_fragments