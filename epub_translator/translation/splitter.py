from dataclasses import dataclass
from typing import Iterator, Generator
from resource_segmentation import split, Resource, Segment

from ..llm import LLM
from .types import Fragment


@dataclass
class Chunk:
  head_remain_tokens: int
  tail_remain_tokens: int
  head_index: int
  body_index: int
  tail_index: int
  fragments_count: int

def split_into_chunks(llm: LLM, fragments_iter: Iterator[Fragment], max_chunk_tokens_count: int):
  for group in split(
    resources=_gen_resources(llm, fragments_iter),
    max_segment_count=max_chunk_tokens_count,
    gap_rate=0.15,
    tail_rate=0.5,
  ):
    head_index: int
    tail_index: int
    fragments_count: int
    body_index, body_end_index = _range_of_group_part(group.body)

    if group.head:
      head_index, head_end_index = _range_of_group_part(group.head)
      assert head_end_index + 1 == body_index, "Head must be continuous with body"
    else:
      head_index = body_index

    if group.tail:
      tail_index, tail_end_index = _range_of_group_part(group.tail)
      fragments_count = tail_end_index - head_index + 1
      assert body_end_index + 1 == tail_index, "Body must be continuous with tail"
    else:
      tail_index = body_end_index + 1
      fragments_count = tail_index - head_index

    yield Chunk(
      head_remain_tokens=group.head_remain_count,
      tail_remain_tokens=group.tail_remain_count,
      head_index=head_index,
      body_index=body_index,
      tail_index=tail_index,
      fragments_count=fragments_count,
    )

def _gen_resources(llm: LLM, fragments_iter: Iterator[Fragment]) -> Generator[Resource[int], None, None]:
  for index, fragment in enumerate(fragments_iter):
    yield Resource(
      count=llm.count_tokens_count(fragment.text),
      start_incision=fragment.start_incision,
      end_incision=fragment.end_incision,
      payload=index,
    )

def _range_of_group_part(target: list[Resource[int] | Segment[int]]) -> tuple[int, int]:
  start_index: int | None = None
  previous_index: int = 0
  for index in _iter_group_part(target):
    if start_index is None:
      start_index = index
    else:
      assert index == previous_index + 1, "Resources in group part must be continuous"
    previous_index = index

  assert start_index is not None, "Group part must contain at least one resource"
  return start_index, previous_index

def _iter_group_part(target: list[Resource[int] | Segment[int]]) -> Generator[int, None, None]:
  for item in target:
    if isinstance(item, Resource):
      yield item.payload
    elif isinstance(item, Segment):
      for resource in item.resources:
        yield resource.payload