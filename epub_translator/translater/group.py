import tiktoken

from dataclasses import dataclass
from typing import Any, Generator, Iterable
from resource_segmentation import split, Segment, Resource, Incision
from .nlp import NLP


@dataclass
class Fragment:
  id: int
  origin: str
  target: str
  tokens: int
  index: int

@dataclass
class _Sentence:
  index: int
  tokens: list[int]
  text: str

class Group:
  def __init__(self, group_max_tokens: int, gap_rate: float) -> None:
    self._encoder: tiktoken.Encoding = tiktoken.get_encoding("o200k_base")
    self._nlp: NLP = NLP()
    self._next_id: int = 0
    self._group_max_tokens: int = group_max_tokens
    self._gap_rate: float = gap_rate

  def split(self, texts: Iterable[str]) -> Generator[tuple[list[Fragment], list[Fragment], list[Fragment]], Any, None]:
    for group in split(
      max_segment_count=self._group_max_tokens,
      gap_rate=self._gap_rate,
      resources=self._gen_resources(texts),
    ):
      head_fragments = self._handle_gap_sentences(
        sentences_iter=self._extract_sentences(group.head),
        remain_tokens=group.head_remain_count,
        clip_head=True,
      )
      body_fragments = self._extract_sentences(group.body)
      tail_fragments = self._handle_gap_sentences(
        sentences_iter=self._extract_sentences(group.tail),
        remain_tokens=group.tail_remain_count,
        clip_head=False,
      )
      yield (
        list(self._to_fragments(head_fragments)),
        list(self._to_fragments(body_fragments)),
        list(self._to_fragments(tail_fragments)),
      )

  def _gen_resources(self, texts: Iterable[str]) -> Generator[Resource[_Sentence], None, None]:
    for index, text in enumerate(texts):
      sentences = self._nlp.split_into_sents(text)
      for i, text in enumerate(sentences):
        sentence = _Sentence(
          text=text,
          index=index,
          tokens=self._encoder.encode(text)
        )
        start_incision: Incision = Incision.MOST_LIKELY
        end_incision: Incision = Incision.MOST_LIKELY

        if i == 0:
          start_incision = Incision.IMPOSSIBLE
        if i == len(sentences) - 1:
          end_incision = Incision.IMPOSSIBLE

        yield Resource(
          count=len(sentence.tokens),
          payload=sentence,
          start_incision=start_incision,
          end_incision=end_incision,
        )

  def _extract_sentences(self, items: list[Resource[_Sentence] | Segment[_Sentence]]) -> Generator[_Sentence, None, None]:
    for item in items:
      if isinstance(item, Resource):
        yield item.payload
      elif isinstance(item, Segment):
        for resource in item.resources:
          yield resource.payload

  def _handle_gap_sentences(
    self,
    sentences_iter: Iterable[_Sentence],
    remain_tokens: int,
    clip_head: bool,
  ) -> Generator[_Sentence, None, None]:

    sentences = list(sentences_iter)

    if self._need_clip(sentences, remain_tokens):
      sentence = sentences[0]
      if clip_head:
        tokens = sentence.tokens[len(sentence.tokens) - remain_tokens:]
      else:
        tokens: list[int] = sentence.tokens[:remain_tokens]

      yield _Sentence(
        index=sentence.index,
        tokens=tokens,
        text=self._encoder.decode(tokens),
      )
    else:
      yield from sentences

  def _need_clip(self, sentences: list[_Sentence], remain_tokens: int) -> bool:
    if len(sentences) == 1:
      sentence = sentences[0]
      if len(sentence.tokens) > remain_tokens:
        return True
    return False

  def _to_fragments(self, sentences: Iterable[_Sentence]):
    fragment: Fragment | None = None
    for sentence in sentences:
      if fragment is None:
        fragment = self._create_fragment(sentence)
      elif fragment.index != sentence.index:
        yield fragment
        fragment = self._create_fragment(sentence)
      else:
        fragment.origin += sentence.text
        fragment.tokens += len(sentence.tokens)
    if fragment is not None:
      yield fragment

  def _create_fragment(self, sentence: _Sentence) -> Fragment:
    fragment = Fragment(
      id=self._next_id,
      index=sentence.index,
      origin=sentence.text,
      target="",
      tokens=len(sentence.tokens),
    )
    self._next_id += 1
    return fragment