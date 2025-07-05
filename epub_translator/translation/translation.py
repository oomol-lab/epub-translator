from typing import Callable, Iterator, Generator
from pathlib import Path
from xml.etree.ElementTree import Element

from ..llm import LLM
from ..xml import encode_friendly
from ..threads import assert_continue

from .types import Fragment, Language
from .store import Store
from .splitter import split_into_chunks
from .chunk import match_fragments, Chunk
from .job import run_translating_job
from .utils import clean_spaces


ProgressReporter = Callable[[float], None]

def translate(
      llm: LLM,
      gen_fragments_iter: Callable[[], Iterator[Fragment]],
      cache_path: Path | None,
      target_language: Language,
      max_chunk_tokens_count: int,
      report_progress: ProgressReporter,
    )-> Generator[str, None, None]:

  store = Store(cache_path) if cache_path else None
  chunk_ranges = list(split_into_chunks(
    llm=llm,
    fragments_iter=gen_fragments_iter(),
    max_chunk_tokens_count=max_chunk_tokens_count,
  ))
  total_tokens_count = sum(chunk.tokens_count for chunk in chunk_ranges)
  translated_tokens_count: int = 0

  for chunk, translated_texts in run_translating_job(
    threads_count=1,
    invoke=lambda chunk: _translate_chunk(
      llm=llm,
      store=store,
      chunk=chunk,
      target_language=target_language,
    ),
    chunks_iter=match_fragments(
      llm=llm,
      chunk_ranges_iter=iter(chunk_ranges),
      fragments_iter=gen_fragments_iter(),
    ),
  ):
    yield from translated_texts
    translated_tokens_count += chunk.tokens_count
    report_progress(float(translated_tokens_count) / total_tokens_count)

def _translate_chunk(llm: LLM, store: Store, chunk: Chunk, target_language: Language) -> list[str]:
    translated_texts: list[str] | None = None
    if store is not None:
      translated_texts = store.get(chunk.hash)

    if translated_texts is None:
      translated_texts = _translate_texts(
        llm=llm,
        target_language=target_language,
        texts=chunk.head + chunk.body + chunk.tail,
      )
    if store is not None:
      store.put(chunk.hash, translated_texts)

    head_length = len(chunk.head)
    translated_texts = translated_texts[head_length:head_length + len(chunk.body)]

    return translated_texts

def _translate_texts(llm: LLM, texts: list[str], target_language: Language):
  assert_continue()
  translated_text = llm.request_text(
    template_name="translate",
    text_tag="TXT",
    user_data="\n".join(clean_spaces(text) for text in texts),
    params={ "target_language": target_language.value },
    parser=lambda r: r,
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

  assert_continue()
  return llm.request_xml(
    template_name="format",
    user_data=request_text,
    params={ "target_language": target_language.value },
    parser=lambda r: _parse_translated_response(r, len(texts)),
  )

def _parse_translated_response(resp_element: Element, sources_count: int) -> list[str]:
  translated_fragments = [""] * sources_count
  for fragment_element in resp_element:
    if fragment_element.text is None:
      continue
    id = fragment_element.get("id", None)
    if id is None:
      continue
    index = int(id) - 1
    if index < 0 or index >= len(translated_fragments):
      raise ValueError(f"invalid fragment id: {id}")
    translated_fragments[index] = fragment_element.text.strip()

  return translated_fragments