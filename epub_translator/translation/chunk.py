from dataclasses import dataclass
from typing import Iterator, Iterable, Generator
from hashlib import sha512
from ..llm import LLM
from .types import Fragment


@dataclass
class Chunk:
  index: int
  hash: bytes
  head: list[str]
  body: list[str]
  tail: list[str]
  tokens_count: int

@dataclass
class ChunkRange:
  index: int
  head_remain_tokens: int
  tail_remain_tokens: int
  head_index: int
  body_index: int
  tail_index: int
  fragments_count: int
  tokens_count: int

  def match(self, index: int) -> bool:
    return self.head_index <= index < self.head_index + self.fragments_count

def match_fragments(
        llm: LLM,
        chunk_ranges_iter: Iterator[ChunkRange],
        fragments_iter: Iterator[Fragment],
      ) -> Generator[Chunk, None, None]:

  for range, texts in _match_range_and_texts(
    chunk_range_iter=chunk_ranges_iter,
    fragments_iter=fragments_iter,
  ):
    head_length = range.body_index - range.head_index
    body_length = range.tail_index - range.body_index
    head = texts[:head_length]
    body = texts[head_length:head_length + body_length]
    tail = texts[head_length + body_length:]

    hash = _hash_texts_list((head, body, tail))
    head = _crop_extra_texts(llm, head, True, range.head_remain_tokens)
    tail = _crop_extra_texts(llm, tail, False, range.tail_remain_tokens)

    yield Chunk(
      hash=hash,
      head=head,
      body=body,
      tail=tail,
      index=range.index,
      tokens_count=range.tokens_count,
    )

def _match_range_and_texts(
      chunk_range_iter: Iterator[ChunkRange],
      fragments_iter: Iterator[Fragment],
    ) -> Generator[tuple[ChunkRange, list[str]], None, None]:

  next_chunk_range: ChunkRange | None = None
  matched_chunk_ranges: list[tuple[ChunkRange, list[str]]] = []

  for index, fragment in enumerate(fragments_iter):
    while True:
      if next_chunk_range is None:
        next_chunk_range = next(chunk_range_iter, None)
        if next_chunk_range is None:
          break
      if not next_chunk_range.match(index):
        break
      matched_chunk_ranges.append((next_chunk_range, []))
      next_chunk_range = None

    if matched_chunk_ranges:
      next_matched_chunks: list[tuple[ChunkRange, list[str]]] = []
      for chunk_range, texts in matched_chunk_ranges:
        if chunk_range.match(index):
          texts.append(fragment.text)
          next_matched_chunks.append((chunk_range, texts))
        else:
          yield chunk_range, texts
      matched_chunk_ranges = next_matched_chunks

  yield from matched_chunk_ranges

def _hash_texts_list(texts_iterable: Iterable[list[str]]) -> bytes:
  is_first = True
  m = sha512()
  for texts in texts_iterable:
    for text in texts:
      if is_first:
        is_first = False
      else:
        m.update(b"\x00")
      m.update(text.encode("utf-8"))
  return m.digest()

def _crop_extra_texts(llm: LLM, texts: list[str], crop_left: bool, remain_tokens_count: int):
  tokens_list: list[list[int]] = [llm.encode_tokens(text) for text in texts]
  remain_texts: list[str] = []

  for tokens in (reversed(tokens_list) if crop_left else tokens_list):
    tokens_count = len(tokens)
    if remain_tokens_count >= tokens_count:
      remain_tokens_count -= tokens_count
      remain_texts.append(llm.decode_tokens(tokens))
      if remain_tokens_count == 0:
        break
    else:
      remain_tokens = tokens[-remain_tokens_count:] if crop_left else tokens[:remain_tokens_count]
      remain_texts.append(llm.decode_tokens(remain_tokens))

  if crop_left:
    remain_texts.reverse()
  return remain_texts