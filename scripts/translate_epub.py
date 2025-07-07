import sys
import os
import json
import shutil

sys.path.append(os.path.abspath(os.path.join(__file__, "..", "..")))

from pathlib import Path
from tqdm import tqdm
from epub_translator import translate, LLM, Language


def main() -> None:
  temp_path = _project_dir_path("temp", clean=True)
  llm=LLM(
    **_read_format_json(),
    log_dir_path=temp_path / "log",
  )
  with tqdm(total=1.0, desc="Translating") as bar:
    def refresh_progress(progress: float) -> None:
      bar.n = progress
      bar.refresh()

    translate(
      llm=llm,
      source_path=Path(__file__).parent.parent / "tests" / "assets" / "治疗精神病.epub",
      translated_path=temp_path / "jap_translated.epub",
      target_language=Language.JAPANESE,
      user_prompt="将“弗洛伊德”翻译为“Freud”，而不是假名。",
      working_path=temp_path,
      report_progress=refresh_progress,
    )

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