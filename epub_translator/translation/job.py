from typing import Iterator, Generator, Callable

from .chunk import Chunk
from ..threads import (
  Interruption,
  WakerDidStop,
  ThreadPool,
  NoMoreExecutions,
  ExecuteFail,
  ExecuteSuccess,
)


def run_translating_job(
      chunks_iter: Iterator[Chunk],
      invoke: Callable[[Chunk], list[str]],
      threads_count: int,
    ) -> Generator[tuple[Chunk, list[str]], None, None]:

  job = _TranslatingJob(threads_count)
  yield from job.run(chunks_iter, invoke)

class _TranslatingJob:
  def __init__(self, threads_count: int):
    self._threads_count: int = threads_count
    self._interruption: Interruption = Interruption()
    self._threads = ThreadPool(self._interruption)
    self._buffer: list[tuple[Chunk, list[str]]] = []
    self._wanna_next_index: int = 0

  def run(self, chunks_iter: Iterator[Chunk], invoke: Callable[[Chunk], list[str]]) -> Generator[tuple[Chunk, list[str]], None, None]:
    self._threads.set_workers(self._threads_count)
    try:
      for chunk in chunks_iter:
        self._threads.execute(
          func=lambda c=chunk: self._invoker(c, invoke),
        )
        while True:
          result = self._threads.pop_result()
          if isinstance(result, NoMoreExecutions):
            break
          elif isinstance(result, ExecuteFail):
            raise RuntimeError("run translating job failed") from result.error
          elif isinstance(result, ExecuteSuccess):
            chunk, translated_texts = result.result
            yield from self._complete_chunk_and_clear_buffer(
              chunk=chunk,
              translated_texts=translated_texts,
            )

    except WakerDidStop:
      pass
    except KeyboardInterrupt as err:
      self._interruption.interrupt()
      raise err
    finally:
      self._threads.set_workers(0)

  def _invoker(self, chunk: Chunk, invoke: Callable[[Chunk], list[str]]) -> tuple[Chunk, list[str]]:
    self._interruption.assert_continue()
    result = invoke(chunk)
    return chunk, result

  def _complete_chunk_and_clear_buffer(
        self,
        chunk: Chunk,
        translated_texts: list[str],
      ) -> Generator[tuple[Chunk, list[str]], None, None]:

    self._buffer.append((chunk, translated_texts))
    if self._wanna_next_index != chunk.index:
      return

    self._buffer.sort(key=lambda e: e[0].index)
    to_clear: list[tuple[Chunk, list[str]]] = []

    for chunk, translated_texts in self._buffer:
      if chunk.index > self._wanna_next_index:
        break
      to_clear.append((chunk, translated_texts))
      if chunk.index == self._wanna_next_index:
        self._wanna_next_index += 1

    if to_clear:
      self._buffer = self._buffer[len(to_clear):]
      yield from to_clear