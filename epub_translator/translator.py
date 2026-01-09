from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from importlib.metadata import version as get_package_version
from os import PathLike
from pathlib import Path

from .epub import (
    Zip,
    read_metadata,
    read_toc,
    search_spine_paths,
    write_metadata,
    write_toc,
)
from .epub_transcode import decode_metadata, decode_toc_list, encode_metadata, encode_toc_list
from .llm import LLM
from .xml import XMLLikeNode, deduplicate_ids_in_element, find_first
from .xml_interrupter import XMLInterrupter
from .xml_translator import FillFailedEvent, XMLTranslator


class _ElementType(Enum):
    TOC = auto()
    METADATA = auto()
    CHAPTER = auto()


@dataclass
class _ElementContext:
    element_type: _ElementType
    chapter_data: tuple[Path, XMLLikeNode] | None = None


def translate(
    source_path: PathLike | str,
    target_path: PathLike | str,
    target_language: str,
    user_prompt: str | None = None,
    max_retries: int = 5,
    max_group_tokens: int = 1200,
    llm: LLM | None = None,
    translation_llm: LLM | None = None,
    fill_llm: LLM | None = None,
    on_progress: Callable[[float], None] | None = None,
    on_fill_failed: Callable[[FillFailedEvent], None] | None = None,
) -> None:
    translation_llm = translation_llm or llm
    fill_llm = fill_llm or llm
    if translation_llm is None:
        raise ValueError("Either translation_llm or llm must be provided")
    if fill_llm is None:
        raise ValueError("Either fill_llm or llm must be provided")

    translator = XMLTranslator(
        translation_llm=translation_llm,
        fill_llm=fill_llm,
        target_language=target_language,
        user_prompt=user_prompt,
        ignore_translated_error=False,
        max_retries=max_retries,
        max_fill_displaying_errors=10,
        max_group_tokens=max_group_tokens,
        cache_seed_content=f"{_get_version()}:{target_language}",
    )
    with Zip(
        source_path=Path(source_path).resolve(),
        target_path=Path(target_path).resolve(),
    ) as zip:
        # mimetype should be the first file in the EPUB ZIP
        zip.migrate(Path("mimetype"))

        total_chapters = sum(1 for _, _ in search_spine_paths(zip))
        toc_list = read_toc(zip)
        metadata_fields = read_metadata(zip)

        # Calculate weights: TOC (5%), Metadata (5%), Chapters (90%)
        toc_has_items = len(toc_list) > 0
        metadata_has_items = len(metadata_fields) > 0
        total_items = (1 if toc_has_items else 0) + (1 if metadata_has_items else 0) + total_chapters

        if total_items == 0:
            return

        interrupter = XMLInterrupter()
        element_contexts: dict[int, _ElementContext] = {}

        toc_weight = 0.05 if toc_has_items else 0
        metadata_weight = 0.05 if metadata_has_items else 0
        chapters_weight = 1.0 - toc_weight - metadata_weight
        progress_per_chapter = chapters_weight / total_chapters if total_chapters > 0 else 0
        current_progress = 0.0

        for translated_elem in translator.translate_elements(
            interrupt_source_text_segments=interrupter.interrupt_source_text_segments,
            interrupt_translated_text_segments=interrupter.interrupt_translated_text_segments,
            interrupt_block_element=interrupter.interrupt_block_element,
            on_fill_failed=on_fill_failed,
            elements=_generate_elements_from_book(
                zip=zip,
                toc_list=toc_list,
                metadata_fields=metadata_fields,
                element_contexts=element_contexts,
            ),
        ):
            elem_id = id(translated_elem)
            context = element_contexts.pop(elem_id, None)

            if context is None:
                continue

            if context.element_type == _ElementType.TOC:
                decoded_toc = decode_toc_list(translated_elem)
                write_toc(zip, decoded_toc)

                current_progress += toc_weight
                if on_progress:
                    on_progress(current_progress)

            elif context.element_type == _ElementType.METADATA:
                decoded_metadata = decode_metadata(translated_elem)
                write_metadata(zip, decoded_metadata)

                current_progress += metadata_weight
                if on_progress:
                    on_progress(current_progress)

            elif context.element_type == _ElementType.CHAPTER:
                if context.chapter_data is not None:
                    chapter_path, xml = context.chapter_data
                    deduplicate_ids_in_element(xml.element)
                    with zip.replace(chapter_path) as target_file:
                        xml.save(target_file)

                current_progress += progress_per_chapter
                if on_progress:
                    on_progress(current_progress)


def _generate_elements_from_book(
    zip: Zip,
    toc_list: list,
    metadata_fields: list,
    element_contexts: dict[int, _ElementContext],
):
    if toc_list:
        toc_elem = encode_toc_list(toc_list)
        elem_id = id(toc_elem)
        element_contexts[elem_id] = _ElementContext(element_type=_ElementType.TOC)
        yield toc_elem

    if metadata_fields:
        metadata_elem = encode_metadata(metadata_fields)
        elem_id = id(metadata_elem)
        element_contexts[elem_id] = _ElementContext(element_type=_ElementType.METADATA)
        yield metadata_elem

    for chapter_path, media_type in search_spine_paths(zip):
        with zip.read(chapter_path) as chapter_file:
            xml = XMLLikeNode(
                file=chapter_file,
                is_html_like=(media_type == "text/html"),
            )
        body_element = find_first(xml.element, "body")
        if body_element is not None:
            elem_id = id(body_element)
            element_contexts[elem_id] = _ElementContext(
                element_type=_ElementType.CHAPTER,
                chapter_data=(chapter_path, xml),
            )
            yield body_element


def _get_version() -> str:
    try:
        return get_package_version("epub-translator")
    except Exception:
        return "development"
