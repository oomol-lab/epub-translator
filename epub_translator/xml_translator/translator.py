from collections.abc import Generator, Iterable
from typing import TypeVar
from xml.etree.ElementTree import Element

from ..llm import LLM, Message, MessageRole
from ..segment import BlockSegment, InlineSegment, TextSegment
from ..xml import decode_friendly, encode_friendly
from .hill_climbing import HillClimbing
from .stream_mapper import XMLStreamMapper
from .submitter import submit_text_segments

T = TypeVar("T")


class XMLTranslator:
    def __init__(
        self,
        llm: LLM,
        stream_mapper: XMLStreamMapper,
        target_language: str,
        user_prompt: str | None,
        ignore_translated_error: bool,
        max_retries: int,
        max_fill_displaying_errors: int,
    ) -> None:
        self._llm: LLM = llm
        self._stream_mapper: XMLStreamMapper = stream_mapper
        self._target_language: str = target_language
        self._user_prompt: str | None = user_prompt
        self._ignore_translated_error: bool = ignore_translated_error
        self._max_retries: int = max_retries
        self._max_fill_displaying_errors: int = max_fill_displaying_errors

    def translate_element(self, element: Element) -> Element:
        for translated in self.translate_elements(((element),)):
            return translated
        raise RuntimeError("Translation failed unexpectedly")

    def translate_elements(self, elements: Iterable[Element]) -> Generator[Element, None, None]:
        for element, text_segments in self._stream_mapper.map_stream(
            elements=iter(elements),
            map=self._translate_inline_segments,
        ):
            yield submit_text_segments(
                element=element,
                text_segments_groups=text_segments,
            )

    def _translate_inline_segments(self, inline_segments: list[InlineSegment]) -> list[list[TextSegment] | None]:
        hill_climbing = HillClimbing(
            encoding=self._llm.encoding,
            max_fill_displaying_errors=self._max_fill_displaying_errors,
            block_segment=BlockSegment(
                root_tag="xml",
                inline_segments=inline_segments,
            ),
        )
        text_segments = (text for inline in inline_segments for text in inline)
        source_text = "".join(self._render_text_segments(text_segments))
        translated_text = self._translate_text(source_text)

        self._request_and_submit(
            hill_climbing=hill_climbing,
            source_text=source_text,
            translated_text=translated_text,
        )
        return list(hill_climbing.gen_text_segments())

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
            return "No complete <xml>...</xml> block found. Please ensure you have properly closed the XML with </xml> tag."  # noqa: E501

        if all_xml_elements > 1:
            return (
                f"Found {all_xml_elements} <xml>...</xml> blocks. "
                "Please return only one XML block without any examples or explanations."
            )
        return first_xml_element
