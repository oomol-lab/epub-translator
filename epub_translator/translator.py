from pathlib import Path

from .epub import Chapter, Zip, search_spine_paths
from .llm import LLM
from .serial import split
from .translation import Translator
from .xml import TruncatableXML, XMLLikeNode


def translate(llm: LLM, source_path: Path, target_path: Path) -> None:
    translator = Translator(
        llm=llm,
        ignore_translated_error=False,
        max_retries=5,
        max_fill_displaying_errors=10,
    )
    with Zip(source_path, target_path) as zip:
        # TODO: Translate TOC...

        # TODO: Translate metadata...

        for chapter_path in search_spine_paths(zip):
            with zip.read(chapter_path) as chapter_file:
                xml = XMLLikeNode(chapter_file)

            chapter = Chapter(xml.element)
            _translate_chapter(
                llm=llm,
                translator=translator,
                chapter=chapter,
            )
            chapter.append_submit()

            with zip.replace(chapter_path) as target_file:
                xml.save(target_file, is_html_like=True)


def _translate_chapter(llm: LLM, translator: Translator, chapter: Chapter):
    for paragraph, translated_element in zip(
        chapter.paragraphs,
        split(
            segments=(TruncatableXML(llm.encoding, p.clone_raw()) for p in chapter.paragraphs),
            transform=lambda paragraphs: translator.translate(p.payload for p in paragraphs),
            max_group_tokens=100,  # TODO: make configurable
        ),
        strict=True,
    ):
        paragraph.submit(translated_element)
