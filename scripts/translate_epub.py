import os
import sys

sys.path.append(os.path.abspath(os.path.join(__file__, "..", "..")))

from pathlib import Path

from tqdm import tqdm

from epub_translator import FillFailedEvent, translate
from epub_translator.language import ENGLISH
from scripts.utils import load_llm, read_and_clean_temp


def main() -> None:
    assets_path = Path(__file__).parent / ".." / "tests" / "assets"
    temp_path = read_and_clean_temp()
    translation_llm, fill_llm = load_llm(
        cache_path=Path(__file__).parent / ".." / "cache",
        log_dir_path=temp_path / "logs",
    )
    with tqdm(total=100, desc="Translating", unit="%", bar_format="{l_bar}{bar}| {n:.1f}/{total:.0f}%") as pbar:
        last_progress = 0.0

        def on_progress(progress: float) -> None:
            nonlocal last_progress
            increment = (progress - last_progress) * 100
            pbar.update(increment)
            last_progress = progress

        def on_fill_failed(event: FillFailedEvent):
            print(f"Retry {event.retried_count} Validation failed:")
            print(f"{event.error_message}")
            print("---\n")
            if event.over_maximum_retries:
                print(
                    "+ ===============================\n"
                    "  Warning: Maximum retries reached without successful XML filling. Will ignore remaining errors.\n"
                    "+ ===============================\n"
                )

        translate(
            translation_llm=translation_llm,
            fill_llm=fill_llm,
            target_language=ENGLISH,
            source_path=assets_path / "治疗精神病.epub",
            target_path=temp_path / "translated.epub",
            on_progress=on_progress,
            on_fill_failed=on_fill_failed,
        )


if __name__ == "__main__":
    main()
