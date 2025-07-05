from typing import Iterator
from .chunk import Chunk

def sort_translated(target: Iterator[tuple[Chunk, list[str]]]) -> Iterator[tuple[Chunk, list[str]]]:
  buffer: list[tuple[Chunk, list[str]]] = []
  wanna_next_index: int = 0

  for chunk, translated_texts in target:
    buffer.append((chunk, translated_texts))
    if wanna_next_index != chunk.index:
      continue

    buffer.sort(key=lambda e: e[0].index)
    to_clear: list[tuple[Chunk, list[str]]] = []

    for chunk, translated_texts in buffer:
      if chunk.index > wanna_next_index:
        break
      to_clear.append((chunk, translated_texts))
      if chunk.index == wanna_next_index:
        wanna_next_index += 1

    if to_clear:
      buffer = buffer[len(to_clear):]
      yield from to_clear