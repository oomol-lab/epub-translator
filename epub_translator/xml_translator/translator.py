from collections.abc import Generator, Iterable
from typing import TypeVar
from xml.etree.ElementTree import Element

from ..iter_sync import IterSync
from ..llm import LLM, Message, MessageRole
from ..xml import encode_friendly
from .fill import XMLFill
from .format import ValidationError
from .group import XMLGroupContext
from .text_segment import TextSegment

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
            fill = XMLFill(text_segments)
            source_text = "".join(self._render_text_segments(text_segments))
            self._fill_into_xml(
                fill=fill,
                translated_text=self._translate_text(source_text),
            )
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

    def _fill_into_xml(self, fill: XMLFill, translated_text: str) -> Element:
        last_error_messages: list[Message] = []
        fixed_messages: list[Message] = [
            Message(
                role=MessageRole.SYSTEM,
                message=self._llm.template("fill").render(),
            ),
            Message(
                role=MessageRole.USER,
                message=f"```XML\n{encode_friendly(fill.request_element)}\n```\n\n{translated_text}",
            ),
        ]
        latest_error: ValidationError | None = None

        for _ in range(self._max_retries):
            response = self._llm.request(
                input=fixed_messages + last_error_messages,
            )
            try:
                return fill.submit_response_text(
                    text=response,
                    errors_limit=self._max_fill_displaying_errors,
                )

            except ValidationError as error:
                latest_error = error
                last_error_messages = [
                    Message(role=MessageRole.ASSISTANT, message=response),
                    Message(role=MessageRole.USER, message=str(error)),
                ]
                # print(f"  ✗ Validation error: {error}")

        message = f"Failed to get valid XML structure after {self._max_retries} attempts"
        if latest_error is None:
            raise ValueError(message)
        else:
            raise ValueError(message) from latest_error
