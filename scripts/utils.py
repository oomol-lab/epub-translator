import json
import shutil
from pathlib import Path

from epub_translator import LLM


def load_llm(**args):
    config = read_format_json()
    translation_config = config.pop("translation", {})
    fill_config = config.pop("fill", {})
    translate_llm = LLM(
        **config,
        **translation_config,
        **args,
    )
    fill_llm = LLM(
        **config,
        **fill_config,
        **args,
    )
    return translate_llm, fill_llm


def read_format_json() -> dict:
    path = Path(__file__).parent / ".." / "format.json"
    path = path.resolve()
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def read_and_clean_temp() -> Path:
    temp_path = Path(__file__).parent / ".." / "temp"
    shutil.rmtree(temp_path, ignore_errors=True)
    temp_path.mkdir(parents=True, exist_ok=True)
    return temp_path.resolve()
