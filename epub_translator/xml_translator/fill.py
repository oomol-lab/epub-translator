from xml.etree.ElementTree import Element

from ..utils import normalize_whitespace
from ..xml import plain_text
from .const import DATA_ORIGIN_LEN_KEY, ID_KEY
from .format import format
from .text_segment import TextSegment, combine_text_segments


class XMLFill:
    def __init__(self, text_segments: list[TextSegment]) -> None:
        self._request_element = Element("xml")
        self._text_segments: dict[tuple[int, ...], list[TextSegment]] = {}  # generated id stack -> text segments

        raw2generated: dict[int, Element] = {}
        raw2generated_ids: dict[int, int] = {}

        for combined_element, sub_raw2generated in combine_text_segments(text_segments):
            unwrapped_parent_ids: set[int] = set()
            sub_element, parents = self._unwrap_parents(combined_element)
            self._request_element.append(sub_element)
            for parent in parents:
                unwrapped_parent_ids.add(id(parent))

            for raw_id, generated_element in sub_raw2generated.items():
                if raw_id in unwrapped_parent_ids:
                    continue
                if id(generated_element) in unwrapped_parent_ids:
                    continue
                generated_id = len(raw2generated)
                raw2generated[raw_id] = generated_element
                raw2generated_ids[raw_id] = generated_id

                generated_text = normalize_whitespace(
                    text=plain_text(generated_element),
                )
                generated_element.attrib = {
                    ID_KEY: str(generated_id),
                    DATA_ORIGIN_LEN_KEY: str(len(generated_text)),
                }

        for text_segment in text_segments:
            generated_id_stack: list[int] = []
            for parent in text_segment.parent_stack:
                generated_id = raw2generated_ids.get(id(parent), None)
                if generated_id is not None:
                    generated_id_stack.append(generated_id)
            generated_key = tuple(generated_id_stack)
            text_segments_stack = self._text_segments.get(generated_key, None)
            if text_segments_stack is None:
                text_segments_stack = []
                self._text_segments[generated_key] = text_segments_stack
            text_segments_stack.append(text_segment)

        for text_segments_stack in self._text_segments.values():
            text_segments_stack.reverse()  # for use call .pop()

    def _unwrap_parents(self, element: Element):
        parents: list[Element] = []
        while True:
            if len(element) != 1:
                break
            child = element[0]
            if not element.text:
                break
            if not child.tail:
                break
            parents.append(element)
            element = child
            element.tail = None
        return element, parents

    @property
    def request_element(self) -> Element:
        return self._request_element

    def submit_response_text(self, text: str, errors_limit: int) -> Element:
        submitted_element = format(
            template_ele=self._request_element,
            validated_text=text,
            errors_limit=errors_limit,
        )
        self._fill_submitted_texts(
            generated_ids_stack=[],
            element=submitted_element,
        )
        return submitted_element

    def _fill_submitted_texts(self, generated_ids_stack: list[int], element: Element):
        current_stack = generated_ids_stack
        generated_id = self._generated_id(element)
        if generated_id >= 0:
            current_stack = generated_ids_stack + [generated_id]

        generated_key = tuple(current_stack)
        text_segments_stack = self._text_segments.get(generated_key, None)
        text = self._normalize_text(element.text)

        if text_segments_stack and text is not None:
            text_segment = text_segments_stack.pop()
            text_segment.text = text

        for child_element in element:
            self._fill_submitted_texts(
                generated_ids_stack=current_stack,
                element=child_element,
            )
            tail = self._normalize_text(child_element.tail)
            if text_segments_stack and tail is not None:
                text_segment = text_segments_stack.pop()
                text_segment.text = tail

    def _generated_id(self, element: Element) -> int:
        str_id = element.get(ID_KEY, None)
        if str_id is None:
            return -1
        try:
            return int(str_id)
        except ValueError:
            return -1

    def _normalize_text(self, text: str | None) -> str | None:
        if text is None:
            return None
        text = normalize_whitespace(text)
        if not text.strip():
            return None
        return text
