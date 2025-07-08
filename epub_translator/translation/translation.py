from typing import Callable, Iterator, Generator
from pathlib import Path
from concurrent.futures import as_completed, ThreadPoolExecutor
from xml.etree.ElementTree import Element

from ..llm import LLM
from ..xml import encode_friendly

from .types import Fragment, Language
from .store import Store
from .splitter import split_into_chunks
from .chunk import match_fragments, Chunk
from .utils import is_empty, clean_spaces


ProgressReporter = Callable[[float], None]

def translate(
      llm: LLM,
      gen_fragments_iter: Callable[[], Iterator[Fragment]],
      cache_path: Path | None,
      target_language: Language,
      user_prompt: str | None,
      max_chunk_tokens_count: int,
      max_threads_count: int,
      report_progress: ProgressReporter,
    ) -> Generator[str, None, None]:

  if user_prompt is not None:
    user_prompt = _normalize_user_input(user_prompt.splitlines())

  store = Store(cache_path) if cache_path else None
  chunk_ranges = list(split_into_chunks(
    llm=llm,
    fragments_iter=gen_fragments_iter(),
    max_chunk_tokens_count=max_chunk_tokens_count,
  ))
  with ThreadPoolExecutor(max_workers=max_threads_count) as executor:
    futures = [
      executor.submit(lambda chunk=chunk: (chunk, _translate_chunk(
        llm=llm,
        store=store,
        chunk=chunk,
        target_language=target_language,
        user_prompt=user_prompt,
      )))
      for chunk in match_fragments(
        llm=llm,
        target_language=target_language,
        chunk_ranges_iter=iter(chunk_ranges),
        fragments_iter=gen_fragments_iter(),
      )
    ]
    def _generate_chunks_from_futures():
      try:
        for future in as_completed(futures):
          yield future.result()
      except Exception as err:
        for future in futures:
          if not future.done():
            future.cancel()
        raise err

    yield from _sort_translated_texts_by_chunk(
      target=_generate_chunks_from_futures(),
      total_tokens_count=sum(chunk.tokens_count for chunk in chunk_ranges),
      report_progress=report_progress,
    )

def _sort_translated_texts_by_chunk(
      target: Iterator[tuple[Chunk, list[str]]],
      total_tokens_count: int,
      report_progress: ProgressReporter,
    ) -> Iterator[list[str]]:

  buffer: list[tuple[Chunk, list[str]]] = []
  wanna_next_index: int = 0
  translated_tokens_count: int = 0

  for chunk, translated_texts in target:
    buffer.append((chunk, translated_texts))
    if wanna_next_index == chunk.index:
      buffer.sort(key=lambda e: e[0].index)
      to_clear: list[list[str]] = []

      for chunk, translated_texts in buffer:
        if chunk.index > wanna_next_index:
          break
        to_clear.append(translated_texts)
        if chunk.index == wanna_next_index:
          wanna_next_index += 1

      if to_clear:
        buffer = buffer[len(to_clear):]
        for translated_texts in to_clear:
          yield from translated_texts

    translated_tokens_count += chunk.tokens_count
    report_progress(float(translated_tokens_count) / total_tokens_count)

def _translate_chunk(
      llm: LLM,
      store: Store,
      chunk: Chunk,
      target_language: Language,
      user_prompt: str | None,
    ) -> list[str]:

    translated_texts: list[str] | None = None
    source_texts = chunk.head + chunk.body + chunk.tail
    if store is not None:
      translated_texts = store.get(chunk.hash)
      if len(source_texts) != len(translated_texts):
        translated_texts = None
        print(f"Warning: Mismatched lengths in cached translation for chunk: {chunk.hash.hex()}",)

    if translated_texts is None:
      translated_texts = [
        clean_spaces(text)
        for text in _translate_texts(
          llm=llm,
          texts=source_texts,
          target_language=target_language,
          user_prompt=user_prompt,
        )
      ]
      if store is not None:
        store.put(chunk.hash, translated_texts)

    head_length = len(chunk.head)
    translated_texts = translated_texts[head_length:head_length + len(chunk.body)]

    return translated_texts

def _translate_texts(
      llm: LLM,
      texts: list[str],
      target_language: Language,
      user_prompt: str | None,
    ) -> list[str]:

  original_text = _normalize_user_input(texts)
  if original_text is None:
    return [""] * len(texts)

  user_data = original_text
  if user_prompt is not None:
    user_data = f"<rules>{user_prompt}</rules>\n\n{original_text}"

  translated_text = llm.request_text(
    template_name="translate",
    text_tag="TXT",
    user_data=user_data,
    parser=lambda r: r,
    params={
      "target_language": target_language.value,
      "user_prompt": user_prompt,
    },
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

  return llm.request_xml(
    template_name="format",
    user_data=request_text,
    params={ "target_language": target_language.value },
    parser=lambda r: _parse_translated_response(r, len(texts)),
  )

def _parse_translated_response(resp_element: Element, sources_count: int) -> list[str]:
  fragments: list[str | None] = [None] * sources_count
  for fragment_element in resp_element:
    if fragment_element.text is None:
      continue
    id = fragment_element.get("id", None)
    if id is None:
      continue
    index = int(id) - 1
    if index < 0 or index >= len(fragments):
      raise ValueError(f"invalid fragment id: {id}")
    fragments[index] = fragment_element.text.strip()

  # 有时 LLM 会将多段融合在一起，这里尽可能让译文靠后，将空白段留在前面。
  # 这样看起来一大段的译文对应若干小段原文，观感更好。
  for i in range(len(fragments)):
    fragment = fragments[i]
    if fragment is not None and i < len(fragments) - 1:
      next_fragment = fragments[i + 1]
      if next_fragment is None:
        fragments[i] = None
        fragments[i + 1] = fragment

  return [f or "" for f in fragments]

def _normalize_user_input(user_lines: list[str]) -> str | None:
  empty_lines_count: int = 0
  lines: list[str] = []
  for line in user_lines:
    if is_empty(line):
      empty_lines_count += 1
    else:
      if lines:
        if empty_lines_count >= 2:
          lines.append("")
          lines.append("")
        elif empty_lines_count == 1:
          lines.append("")
      lines.append(clean_spaces(line))
  if not lines:
    return None
  return "\n".join(lines)