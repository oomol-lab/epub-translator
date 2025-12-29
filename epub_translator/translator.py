from pathlib import Path
from xml.etree.ElementTree import Element

from .epub import Placeholder, Zip, read_toc, search_spine_paths, write_toc
from .epub.common import find_opf_path
from .llm import LLM
from .translation import XMLGroupContext, XMLTranslator
from .xml import XMLLikeNode, deduplicate_ids_in_element, plain_text


def translate(
    llm: LLM,
    source_path: Path,
    target_path: Path,
    target_language: str,
    user_prompt: str | None = None,
) -> None:
    translator = XMLTranslator(
        llm=llm,
        target_language=target_language,
        user_prompt=user_prompt,
        ignore_translated_error=False,
        max_retries=5,
        max_fill_displaying_errors=10,
        group_context=XMLGroupContext(
            encoding=llm.encoding,
            max_group_tokens=1000,  # TODO: make configurable
        ),
    )
    with Zip(source_path, target_path) as zip:
        # Translate TOC
        _translate_toc(translator, zip)

        # Translate metadata
        _translate_metadata(translator, zip)

        for _, (chapter_path, xml, placeholder) in translator.translate_items(_search_chapter_items(zip)):
            placeholder.recover()
            deduplicate_ids_in_element(xml.element)
            with zip.replace(chapter_path) as target_file:
                xml.save(target_file, is_html_like=True)


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


def _search_chapter_items(zip: Zip):
    for chapter_path in search_spine_paths(zip):
        with zip.read(chapter_path) as chapter_file:
            xml = XMLLikeNode(chapter_file)
        placeholder = Placeholder(xml.element)
        yield xml.element, (chapter_path, xml, placeholder)


def _create_text_element(text: str) -> Element:
    elem = Element("text")
    elem.text = text
    return elem
