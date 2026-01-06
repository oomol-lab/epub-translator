import os
import sys

sys.path.append(os.path.abspath(os.path.join(__file__, "..", "..")))

from pathlib import Path

from tqdm import tqdm

from epub_translator import LLM, translate
from epub_translator.language import ENGLISH
from scripts.utils import read_and_clean_temp, read_format_json


def main() -> None:
    config = read_format_json()
    assets_path = Path(__file__).parent / ".." / "tests" / "assets"
    temp_path = read_and_clean_temp()
    cache_path = Path(__file__).parent / ".." / "cache"
    log_dir_path = temp_path / "logs"

    # Extract separate parameters for translate and fill tasks
    translate_temperature = config.pop("translate_temperature", 0.8)
    translate_top_p = config.pop("translate_top_p", 0.6)
    fill_temperature = config.pop("fill_temperature", 0.3)
    fill_top_p = config.pop("fill_top_p", 0.7)

    # Create two LLM instances with different configurations
    translate_llm = LLM(
        **config,
        temperature=translate_temperature,
        top_p=translate_top_p,
        log_dir_path=log_dir_path,
        cache_path=cache_path,
    )

    fill_llm = LLM(
        **config,
        temperature=fill_temperature,
        top_p=fill_top_p,
        log_dir_path=log_dir_path,
        cache_path=cache_path,
    )

    with tqdm(total=100, desc="Translating", unit="%", bar_format="{l_bar}{bar}| {n:.1f}/{total:.0f}%") as pbar:
        last_progress = 0.0

        def on_progress(progress: float) -> None:
            nonlocal last_progress
            increment = (progress - last_progress) * 100
            pbar.update(increment)
            last_progress = progress

        translate(
            translate_llm=translate_llm,
            fill_llm=fill_llm,
            target_language=ENGLISH,
            source_path=assets_path / "治疗精神病.epub",
            target_path=temp_path / "translated.epub",
            on_progress=on_progress,
        )


if __name__ == "__main__":
    main()
