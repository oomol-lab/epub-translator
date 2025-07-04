import sys
import os
import json
import shutil

sys.path.append(os.path.abspath(os.path.join(__file__, "..", "..")))

from pathlib import Path
from resource_segmentation import Incision
from epub_translator import LLM, Language
from epub_translator.translation import translate, Fragment


def main() -> None:
  temp_path = _project_dir_path("temp", clean=True)
  llm=LLM(
    **_read_format_json(),
    log_dir_path=temp_path / "log",
  )
  translated = translate(
    llm=llm,
    cache_path=temp_path / "cache",
    target_language=Language.ENGLISH,
    max_chunk_tokens_count=4096,
    gen_fragments_iter=lambda:(
      Fragment(text=text, start_incision=Incision.IMPOSSIBLE, end_incision=Incision.IMPOSSIBLE)
      for text in (
        "分析者和他的每个家人之间发生的斗争逐渐聚焦起来，最初的事件或情境（我在这儿将其称为S）。",
        "基于迄今为止在分析中所阐述的内容，被赋予了一系列的意义一这些意义并不一定相互抵消或相互矛盾，但每一个意义都呈现了问题的一条线索（换句话说，在这里，我将后来的每一个事件或情境称为S2）。",
        "一个神经症分析者试图通过这种方式，在事件发生数年甚至数十年后，回溯性地绑住或固定一个较早事件的意义，每一次重新解读都可以起到暂时性地锚定（法语capitonner）其意义的作用，有些重新解读要比其他的重新解读更长时间地绑住其意义。",
        "要注意到，这个工作具有替代性隐喻的结构，在某种意义上，一个解释（用词语或能指来表达的)替代了另一个解释，一个新的解释替代了旧的解释。",
      )
    ),
  )
  for text in translated:
    print(">>", text)

def _read_format_json() -> dict:
  path = Path(__file__) / ".." / ".." / "format.json"
  path = path.resolve()
  with open(path, mode="r", encoding="utf-8") as file:
    return json.load(file)

def _project_dir_path(name: str, clean: bool = False) -> Path:
  path = Path(__file__) / ".." / ".." / name
  path = path.resolve()
  if clean:
    shutil.rmtree(path, ignore_errors=True)
  path.mkdir(parents=True, exist_ok=True)
  return path


if __name__ == "__main__":
  main()