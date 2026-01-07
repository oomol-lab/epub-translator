from collections.abc import Callable, Generator
from pathlib import Path
from xml.etree.ElementTree import Element

from .epub import Placeholder, Zip, is_placeholder_tag, read_toc, search_spine_paths, write_toc
from .epub.common import find_opf_path
from .llm import LLM
from .xml import XMLLikeNode, deduplicate_ids_in_element, find_first, plain_text
from .xml_translator import XMLTranslator


def translate(
    source_path: Path,
    target_path: Path,
    target_language: str,
    user_prompt: str | None = None,
    max_retries: int = 5,
    max_group_tokens: int = 1200,
    llm: LLM | None = None,
    translation_llm: LLM | None = None,
    fill_llm: LLM | None = None,
    on_progress: Callable[[float], None] | None = None,
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
    )
    with Zip(source_path, target_path) as zip:
        # Progress distribution: TOC 3%, metadata 2%, chapters 95%
        TOC_PROGRESS = 0.03
        METADATA_PROGRESS = 0.02
        CHAPTERS_PROGRESS = 0.95

        # Count total chapters for progress calculation (lightweight, no content loading)
        total_chapters = _count_chapters(zip)
        chapter_progress_step = CHAPTERS_PROGRESS / total_chapters if total_chapters > 0 else 0

        current_progress = 0.0

        # Translate TOC
        _translate_toc(translator, zip)
        current_progress += TOC_PROGRESS
        if on_progress:
            on_progress(current_progress)

        # Translate metadata
        _translate_metadata(translator, zip)
        current_progress += METADATA_PROGRESS
        if on_progress:
            on_progress(current_progress)

        # Translate chapters
        processed_chapters = 0
        for _ in _translate_chapters(translator, zip):
            # Update progress after each chapter
            processed_chapters += 1
            current_progress = TOC_PROGRESS + METADATA_PROGRESS + (processed_chapters * chapter_progress_step)
            if on_progress:
                on_progress(current_progress)


def _translate_toc(translator: XMLTranslator, zip: Zip):
    """Translate TOC (Table of Contents) titles."""
    toc_list = read_toc(zip)
    if not toc_list:
        return

    # Collect all titles recursively
    titles_to_translate: list[str] = []

    def collect_titles(items):
        for item in items:
            titles_to_translate.append(item.title)
            if item.children:
                collect_titles(item.children)

    collect_titles(toc_list)

    # Create XML elements for translation
    elements_to_translate = Element("toc")
    elements_to_translate.extend(_create_text_element(title) for title in titles_to_translate)

    # Translate all titles at once
    translated_element = translator.translate_element(elements_to_translate)

    # Extract translated texts
    from builtins import zip as builtin_zip

    translated_titles = [
        plain_text(elem) if elem is not None else original
        for elem, original in builtin_zip(translated_element, titles_to_translate)
    ]

    # Fill back translated titles
    title_index = 0

    def fill_titles(items):
        nonlocal title_index
        for item in items:
            item.title = translated_titles[title_index]
            title_index += 1
            if item.children:
                fill_titles(item.children)

    fill_titles(toc_list)

    # Write back the translated TOC
    write_toc(zip, toc_list)


def _translate_metadata(translator: XMLTranslator, zip: Zip):
    """Translate metadata fields in OPF file."""
    opf_path = find_opf_path(zip)

    with zip.read(opf_path) as f:
        xml = XMLLikeNode(f)

    # Find metadata element
    metadata_elem = None
    for child in xml.element:
        if child.tag.endswith("metadata"):
            metadata_elem = child
            break

    if metadata_elem is None:
        return

    # Collect metadata fields to translate
    # Skip fields that should not be translated
    skip_fields = {
        "language",
        "identifier",
        "date",
        "meta",
        "contributor",  # Usually technical information
    }

    fields_to_translate: list[tuple[Element, str]] = []

    for elem in metadata_elem:
        # Get tag name without namespace
        tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        # Check if element has text content and should be translated
        if elem.text and elem.text.strip() and tag_name not in skip_fields:
            fields_to_translate.append((elem, elem.text.strip()))

    if not fields_to_translate:
        return

    # Create XML elements for translation
    elements_to_translate = Element("metadata")
    elements_to_translate.extend(_create_text_element(text) for _, text in fields_to_translate)

    # Translate all metadata at once
    translated_element = translator.translate_element(elements_to_translate)

    # Fill back translated texts
    from builtins import zip as builtin_zip

    for (elem, _), translated_elem in builtin_zip(fields_to_translate, translated_element, strict=True):
        if translated_elem is not None:
            translated_text = plain_text(translated_elem)
            if translated_text:
                elem.text = translated_text

    # Write back the modified OPF file
    with zip.replace(opf_path) as f:
        xml.save(f)


def _translate_chapters(translator: XMLTranslator, zip: Zip) -> Generator[Path, None, None]:
    items_cache: dict[int, tuple[Path, XMLLikeNode, Placeholder]] = {}
    for body_element in translator.translate_elements(
        elements=_search_chapter_items(zip, items_cache),
        filter_text_segments=lambda segment: not any(is_placeholder_tag(e.tag) for e in segment.parent_stack),
    ):
        item = items_cache.pop(id(body_element), None)
        if item is not None:
            chapter_path, xml, placeholder = item
            placeholder.recover()
            deduplicate_ids_in_element(xml.element)
            with zip.replace(chapter_path) as target_file:
                xml.save(target_file)
            yield chapter_path


def _count_chapters(zip: Zip) -> int:
    """Count total chapters without loading content (lightweight)."""
    return sum(1 for _ in search_spine_paths(zip))


def _search_chapter_items(zip: Zip, items_cache: dict[int, tuple[Path, XMLLikeNode, Placeholder]]):
    for chapter_path in search_spine_paths(zip):
        with zip.read(chapter_path) as chapter_file:
            xml = XMLLikeNode(
                file=chapter_file,
                is_html_like=chapter_path.suffix.lower() in (".html", ".htm"),
            )
        body_element = find_first(xml.element, "body")
        if body_element is not None:
            placeholder = Placeholder(body_element)
            items_cache[id(body_element)] = (chapter_path, xml, placeholder)
            yield body_element


def _create_text_element(text: str) -> Element:
    elem = Element("text")
    elem.text = text
    return elem
