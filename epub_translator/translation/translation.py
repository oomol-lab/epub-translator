from typing import Callable, Iterator, Generator
from pathlib import Path
from xml.etree.ElementTree import Element

from ..llm import LLM
from ..xml import encode_friendly
from .types import Fragment
from .store import Store
from .splitter import split_into_chunks
from .chunk import match_fragments
from .utils import clean_spaces


def translate(
      llm: LLM,
      gen_fragments_iter: Callable[[], Iterator[Fragment]],
      cache_path: Path | None,
      max_chunk_tokens_count: int,
    )-> Generator[str, None, None]:

  store = Store(cache_path) if cache_path else None
  chunk_ranges = list(split_into_chunks(
    llm=llm,
    fragments_iter=gen_fragments_iter(),
    max_chunk_tokens_count=max_chunk_tokens_count,
  ))
  for chunk in match_fragments(
    llm=llm,
    chunk_ranges_iter=iter(chunk_ranges),
    fragments_iter=gen_fragments_iter(),
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

def _translate_texts(llm: LLM, texts: list[str]):
  target_language = "英语"
  translated_text = llm.request_txt(
    template_name="translate",
    user_data=" ".join(clean_spaces(text) for text in texts),
    params={ "target_language": target_language },
  )
  request_element = Element("request")

  for i, fragment in enumerate(texts):
    fragment_element = Element("fragment", attrib={
      "id": str(i + 1),
    })
    fragment_element.text = clean_spaces(fragment)
    request_element.append(fragment_element)

  request_element_text = encode_friendly(request_element)
  request_text = f"```XML\n{request_element_text}\n```\n\n{translated_text}"
  resp_element = llm.request_xml(
    template_name="format",
    user_data=request_text,
    params={ "target_language": target_language },
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