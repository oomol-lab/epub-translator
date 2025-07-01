import re
import os

from typing import Callable, Iterable
from hashlib import sha256

from .group import Group, Fragment
from json import loads, dumps
from .llm import LLM


_LAN_FULL_NAMES: dict[str, str] = {
  "en": "English",
  "cn": "simplified Chinese",
  "ja": "Japanese",
  "fr": "French",
  "ru": "Russian",
  "de": "German",
}

class Translator:
  def __init__(
        self,
        group_max_tokens: int,
        cache_path: str,
        key: str | None,
        url: str | None,
        model: str,
        temperature: float,
        timeout: float | None,
        source_lan: str,
        target_lan: str,
        streaming: bool) -> None:

    self._streaming: bool = streaming
    self._group: Group = Group(
      group_max_tokens=group_max_tokens,
      gap_rate=0.1,
    )
    self._cache_path: str = cache_path
    self._llm = LLM(
      key=key,
      url=url,
      model=model,
      temperature=temperature,
      timeout=timeout,
    )
    self._admin_prompt: str = _gen_admin_prompt(
      source_lan=self._lan_full_name(source_lan),
      target_lan=self._lan_full_name(target_lan),
    )

  def translate(self, source_texts: list[str], report_progress: Callable[[float], None]) -> list[str]:
    body_fragments: list[Fragment] = []
    target_texts: list[str] = [""] * len(source_texts)
    splitted = list(self._group.split(source_texts))

    for i, (head, body, tail) in enumerate(splitted):
      body_fragments.extend(body)
      self._translate_fragments(
        fragments=head + body + tail,
        report_progress=lambda p, i=i: report_progress(
          (float(i) + p) / len(splitted),
        ),
      )
    for fragment in body_fragments:
      target_texts[fragment.index] += fragment.target

    return target_texts

  def _translate_fragments(self, fragments: list[Fragment], report_progress: Callable[[float], None]) -> list[Fragment]:
    texts: list[str] = []
    translated_texts: list[str] = []
    indexes: list[int] = []
    for index, fragment in enumerate(fragments):
      text = fragment.origin.strip()
      if text != "":
        texts.append(text)
        indexes.append(index)

    if len(texts) > 0:
      for i, text in enumerate(self._translate_text_by_text(texts)):
        report_progress(min(1.0, float(i) / float(len(texts))))
        translated_texts.append(text)
    report_progress(1.0)

    for index, text in zip(indexes, translated_texts):
      fragments[index].target = text
    return fragments

  def _translate_text_by_text(self, texts: list[str]):
    hash = self._to_hash(texts)
    cache_file_path = os.path.join(self._cache_path, f"{hash}.json")
    if os.path.exists(cache_file_path):
      with open(cache_file_path, "r", encoding="utf-8") as cache_file:
        for translated_text in loads(cache_file.read()):
          yield translated_text
    else:
      system=self._admin_prompt
      human="\n".join([f"{i+1}: {t}" for i, t in enumerate(texts)])
      translated_texts: list[str] = []
      iter_lines: Iterable[str]

      if self._streaming:
        iter_lines = self._llm.invoke_response_lines(system, human)
      else:
        iter_lines = self._llm.invoke(system, human).split("\n")
      for line in iter_lines:
        match = re.search(r"^\d+\:", line)
        if match:
          translated_text = re.sub(r"^\d+\:\s*", "", line)
          yield translated_text
          translated_texts.append(translated_text)

      with open(cache_file_path, "w", encoding="utf-8") as cache_file:
        cache_file.write(dumps(
          obj=translated_texts,
          ensure_ascii=False,
          indent=2,
        ))


  def _lan_full_name(self, name: str) -> str:
    full_name = _LAN_FULL_NAMES.get(name, None)
    if full_name is None:
      full_name = _LAN_FULL_NAMES["en"]
    return full_name

  def _to_hash(self, texts: list[str]) -> str:
    hash = sha256()
    for text in texts:
      data = text.encode(encoding="utf-8")
      hash.update(data)
      hash.update(b"\x03") # ETX means string's end
    return hash.hexdigest()

def _gen_admin_prompt(target_lan: str, source_lan: str) -> str:
  return f"""
You are a translator and need to translate the user's {source_lan} text into {target_lan}.
I want you to replace simplified A0-level words and sentences with more beautiful and elegant, upper level {target_lan} words and sentences. Keep the meaning same, but make them more literary.
I want you to only reply the translation and nothing else, do not write explanations.
A number and colon are added to the top of each line of text entered by the user. This number is only used to align the translation text for you and has no meaning in itself. You should delete the number in your mind to understand the user's original text.
Your translation results should be split into a number of lines, the number of lines is equal to the number of lines in the user's original text. The content of each line should correspond to the corresponding line of the user's original text.
All user submitted text must be translated. The translated lines must not be missing, added, misplaced, or have their order changed. They must correspond exactly to the original text of the user.

Here is an example. First, the user submits the original text in English (this is just an example):
1: IV
2: This true without lying, certain & most true:
3: That which is below is like that which is above and that which is above is like that which is below to do ye miracles of one only thing.
4: .+
5: And as all things have been and arose from one by ye mediation of one: so all things have their birth from this one thing by adaptation.

If you are asked to translate into Chinese, you need to submit the translated content in the following format:
1: 四
2: 这是真的，没有任何虚妄，是确定的，最真实的：
3: 上如其下，下如其上，以此来展现“一”的奇迹。
4: .+
5: 万物皆来自“一”的沉思，万物在“一”的安排下诞生。
"""