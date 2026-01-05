from collections.abc import Generator, Iterable
from typing import TypeVar
from xml.etree.ElementTree import Element

from ..iter_sync import IterSync
from ..llm import LLM, Message, MessageRole
from ..segment import TextSegment
from ..xml import decode_friendly, encode_friendly
from .group import XMLGroupContext
from .hill_climbing import HillClimbing

T = TypeVar("T")


class XMLTranslator:
    def __init__(
        self,
        llm: LLM,
        group_context: XMLGroupContext,
        target_language: str,
        user_prompt: str | None,
        ignore_translated_error: bool,
        max_retries: int,
        max_fill_displaying_errors: int,
    ) -> None:
        self._llm: LLM = llm
        self._group_context: XMLGroupContext = group_context
        self._target_language: str = target_language
        self._user_prompt: str | None = user_prompt
        self._ignore_translated_error: bool = ignore_translated_error
        self._max_retries: int = max_retries
        self._max_fill_displaying_errors: int = max_fill_displaying_errors

    def translate_to_element(self, element: Element) -> Element:
        for translated, _, _ in self.translate_to_text_segments(((element, None),)):
            return translated
        raise RuntimeError("Translation failed unexpectedly")

    def translate_to_text_segments(
        self, items: Iterable[tuple[Element, T]]
    ) -> Generator[tuple[Element, list[TextSegment], T], None, None]:
        sync: IterSync[tuple[Element, T]] = IterSync()
        text_segments: list[TextSegment] = []

        for text_segment in self._translate_text_segments(
            elements=(e for e, _ in sync.iter(items)),
        ):
            while True:
                if sync.tail is None:
                    break
                tail_element, _ = sync.tail
                if id(tail_element) == id(text_segment.root):
                    break
                tail_element, payload = sync.take()
                yield tail_element, text_segments, payload
                text_segments = []
            text_segments.append(text_segment)

        while sync.tail is not None:
            tail_element, payload = sync.take()
            yield tail_element, text_segments, payload
            text_segments = []

    def _translate_text_segments(self, elements: Iterable[Element]):
        for group in self._group_context.split_groups(elements):
            text_segments = list(group)
            source_text = "".join(self._render_text_segments(text_segments))
            translated_text = self._translate_text(source_text)
            hill_climbing = HillClimbing(
                encoding=self._llm.encoding,
                request_tag="xml",
                text_segments=text_segments,
                max_fill_displaying_errors=self._max_fill_displaying_errors,
            )
            self._request_and_submit(
                hill_climbing=hill_climbing,
                source_text=source_text,
                translated_text=translated_text,
            )
            hill_climbing.append()
            yield from group.body

    def _render_text_segments(self, segments: Iterable[TextSegment]):
        iterator = iter(segments)
        segment = next(iterator, None)
        if segment is None:
            return
        while True:
            next_segment = next(iterator, None)
            if next_segment is None:
                break
            yield segment.text
            if id(segment.block_parent) != id(next_segment.block_parent):
                yield "\n\n"
            segment = next_segment
        yield segment.text

    def _translate_text(self, text: str) -> str:
        return self._llm.request(
            input=[
                Message(
                    role=MessageRole.SYSTEM,
                    message=self._llm.template("translate").render(
                        target_language=self._target_language,
                        user_prompt=self._user_prompt,
                    ),
                ),
                Message(role=MessageRole.USER, message=text),
            ]
        )

    def _request_and_submit(self, hill_climbing: HillClimbing, source_text: str, translated_text: str) -> None:
        user_message = (
            f"Source text:\n{source_text}\n\n"
            f"XML template:\n```XML\n{encode_friendly(hill_climbing.request_element())}\n```\n\n"
            f"Translated text:\n{translated_text}"
        )
        fixed_messages: list[Message] = [
            Message(
                role=MessageRole.SYSTEM,
                message=self._llm.template("fill").render(),
            ),
            Message(
                role=MessageRole.USER,
                message=user_message,
            ),
        ]
        conversation_history: list[Message] = []

        with self._llm.context() as llm_context:
            did_success: bool = False
            for _ in range(self._max_retries):
                response = llm_context.request(fixed_messages + conversation_history)
                validated_element = self._extract_xml_element(response)
                error_message: str | None = None

                if isinstance(validated_element, str):
                    error_message = validated_element
                elif isinstance(validated_element, Element):
                    error_message = hill_climbing.submit(validated_element)

                if error_message is None:
                    did_success = True
                    break

                conversation_history = [
                    Message(role=MessageRole.ASSISTANT, message=response),
                    Message(role=MessageRole.USER, message=error_message),
                ]
            if not did_success:
                print("Warning: Maximum retries reached without successful XML filling. Will ignore remaining errors.")

    def _extract_xml_element(self, text: str) -> Element | str:
        first_xml_element: Element | None = None
        all_xml_elements: int = 0

        for xml_element in decode_friendly(text, tags="xml"):
            if first_xml_element is None:
                first_xml_element = xml_element
            all_xml_elements += 1

        if first_xml_element is None:
            return "No complete <xml>...</xml> block found. Please ensure you have properly closed the XML with </xml> tag."

        if all_xml_elements > 1:
            return (
                f"Found {all_xml_elements} <xml>...</xml> blocks. "
                "Please return only one XML block without any examples or explanations."
            )
        return first_xml_element
