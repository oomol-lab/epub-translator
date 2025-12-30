import os
import sys

sys.path.append(os.path.abspath(os.path.join(__file__, "..", "..")))

from pathlib import Path

from tqdm import tqdm

from epub_translator import LLM, translate
from scripts.utils import read_and_clean_temp, read_format_json


def main() -> None:
    config = read_format_json()
    assets_path = Path(__file__).parent / ".." / "tests" / "assets"
    temp_path = read_and_clean_temp()
    llm = LLM(
        **config,
        log_dir_path=temp_path / "logs",
        cache_path=temp_path / "cache",
    )
    with tqdm(total=100, desc="Translating", unit="%", bar_format="{l_bar}{bar}| {n:.1f}/{total:.0f}%") as pbar:
        last_progress = 0.0

        def on_progress(progress: float) -> None:
            nonlocal last_progress
            increment = (progress - last_progress) * 100
            pbar.update(increment)
            last_progress = progress

        translate(
            llm=llm,
            target_language="English",
            source_path=assets_path / "治疗精神病.epub",
            target_path=temp_path / "translated.epub",
            on_progress=on_progress,
        )


if __name__ == "__main__":
    main()
