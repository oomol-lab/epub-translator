from collections.abc import Generator, Iterable
from typing import TypeVar
from xml.etree.ElementTree import Element

from ..iter_sync import IterSync
from ..llm import LLM, Message, MessageRole
from ..xml import encode_friendly
from .fill import XMLFill
from .format import ValidationError, _extract_xml_element
from .group import XMLGroupContext
from .progressive_locking import ProgressiveLockingValidator
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
            translated_text = self._translate_text(source_text)
            self._fill_into_xml(
                fill=fill,
                source_text=source_text,
                translated_text=translated_text,
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

    def _fill_into_xml(self, fill: XMLFill, source_text: str, translated_text: str) -> Element:
        user_message = (
            f"Source text:\n{source_text}\n\n"
            f"XML template:\n```XML\n{encode_friendly(fill.request_element)}\n```\n\n"
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

        validator = ProgressiveLockingValidator()
        conversation_history: list[Message] = []
        latest_error: ValidationError | None = None

        for _ in range(self._max_retries):
            # Request LLM response
            response = self._llm.request(
                input=fixed_messages + conversation_history,
            )

            try:
                # Extract XML from response
                validated_element = _extract_xml_element(response)

                # Validate with progressive locking
                is_complete, error_message, newly_locked = validator.validate_with_locking(
                    template_ele=fill.request_element,
                    validated_ele=validated_element,
                    errors_limit=self._max_fill_displaying_errors,
                )

                if is_complete:
                    # All nodes locked, fill successful
                    fill._fill_submitted_texts(  # pylint: disable=protected-access
                        generated_ids_stack=[],
                        element=validated_element,
                    )
                    return validated_element

                # Not complete yet, construct error message with progress info
                progress_msg = f"Progress: {len(validator.locked_ids)} nodes locked"
                if newly_locked:
                    progress_msg += f", {len(newly_locked)} newly locked this round"

                full_error_message = f"{progress_msg}\n\n{error_message}"

                conversation_history = [
                    Message(role=MessageRole.ASSISTANT, message=response),
                    Message(role=MessageRole.USER, message=full_error_message),
                ]

            except ValidationError as error:
                # XML extraction or basic validation failed
                latest_error = error
                conversation_history = [
                    Message(role=MessageRole.ASSISTANT, message=response),
                    Message(role=MessageRole.USER, message=str(error)),
                ]

        message = f"Failed to get valid XML structure after {self._max_retries} attempts"
        if latest_error is None:
            raise ValueError(message)
        else:
            raise ValueError(message) from latest_error
