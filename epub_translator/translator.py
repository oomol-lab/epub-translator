from pathlib import Path
from xml.etree.ElementTree import Element

from tiktoken import Encoding, get_encoding

from .epub import Chapter, Zip, search_spine_paths
from .serial import split
from .translation import Translator
from .xml import TruncatableXML, XMLLikeNode


def translate(source_path: Path, target_path: Path, token_encoding: str = "o200k_base") -> None:
    encoding: Encoding = get_encoding(token_encoding)
    translator = Translator()
    with Zip(source_path, target_path) as zip:
        # TODO: Translate TOC...

        # TODO: Translate metadata...

        for chapter_path in search_spine_paths(zip):
            with zip.read(chapter_path) as chapter_file:
                xml = XMLLikeNode(chapter_file)

            chapter = Chapter(xml.element)
            _translate_chapter(
                translator=translator,
                encoding=encoding,
                chapter=chapter,
            )
            chapter.append_submit()

            with zip.replace(chapter_path) as target_file:
                xml.save(target_file, is_html_like=True)


def _translate_chapter(translator: Translator, encoding: Encoding, chapter: Chapter):
    for paragraph, translated_element in zip(
        chapter.paragraphs,
        split(
            segments=(TruncatableXML(encoding, p.clone_raw()) for p in chapter.paragraphs),
            transform=lambda elements: _translate_paragraphs(translator, elements),
            max_group_tokens=100,  # TODO: make configurable
        ),
        strict=True,
    ):
        paragraph.submit(translated_element)


def _translate_paragraphs(translator: Translator, paragraph_elements: list[TruncatableXML]) -> list[Element]:
    root = Element("xml")
    for paragraph_element in paragraph_elements:
        root.append(paragraph_element._payload)

    return list(
        translator.translate(
            text="\n\n".join(p.text for p in paragraph_elements),
            element=root,
        )
    )
