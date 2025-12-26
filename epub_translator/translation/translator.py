from collections.abc import Iterable
from xml.etree.ElementTree import Element

from ..llm import LLM, Message, MessageRole
from ..utils import normalize_whitespace
from ..xml import encode_friendly, iter_with_stack, plain_text
from .format import ValidationError, format
from .xml_processor import XMLProcessor


class Translator:
    def __init__(
        self,
        llm: LLM,
        target_language: str,
        user_prompt: str | None,
        ignore_translated_error: bool,
        max_retries: int,
        max_fill_displaying_errors: int,
    ) -> None:
        self._llm: LLM = llm
        self._target_language: str = target_language
        self._user_prompt: str | None = user_prompt
        self._ignore_translated_error: bool = ignore_translated_error
        self._max_retries: int = max_retries
        self._max_fill_displaying_errors: int = max_fill_displaying_errors

    def translate(self, elements: Iterable[Element]) -> list[Element | None]:
        raw_element = Element("xml")
        raw_element.extend(elements)
        translated_element = self._translate_element(raw_element)
        translated_elements: list[Element | None]

        if translated_element is not None:
            translated_elements = list(translated_element)
        else:
            translated_elements = [
                Element(
                    sub_raw_element.tag,
                    sub_raw_element.attrib,
                )
                for sub_raw_element in raw_element
            ]
        for i in range(len(translated_elements)):
            element = translated_elements[i]
            if element is not None:
                translated_elements[i] = self._process_translated_element(element)
        return translated_elements

    def _translate_element(self, element: Element) -> Element | None:
        xml_processor = XMLProcessor(root=element)
        if xml_processor.processed is None:
            return None

        source_text = plain_text(xml_processor.processed)
        translated_text = self._translate_text(source_text)

        return self._fill_into_xml(
            xml_processor=xml_processor,
            translated_text=translated_text,
        )

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

    def _fill_into_xml(self, xml_processor: XMLProcessor, translated_text: str) -> Element | None:
        processed = xml_processor.processed
        assert processed is not None

        last_error_messages: list[Message] = []
        fixed_messages: list[Message] = [
            Message(
                role=MessageRole.SYSTEM,
                message=self._llm.template("fill").render(),
            ),
            Message(
                role=MessageRole.USER,
                message=f"```XML\n{encode_friendly(processed)}\n```\n\n{translated_text}",
            ),
        ]
        formatted_element: Element | None = None
        latest_error: ValidationError | None = None

        for _ in range(self._max_retries):
            response = self._llm.request(
                input=fixed_messages + last_error_messages,
            )
            try:
                formatted_element = format(
                    template_ele=processed,
                    validated_text=response,
                    errors_limit=self._max_fill_displaying_errors,
                )
                break

            except ValidationError as error:
                latest_error = error
                if self._ignore_translated_error and error.validated_ele is not None:
                    formatted_element = error.validated_ele
                last_error_messages = [
                    Message(role=MessageRole.ASSISTANT, message=response),
                    Message(role=MessageRole.USER, message=str(error)),
                ]
                # print(f"  ✗ Validation error: {error}")

        if formatted_element is None:
            message = f"Failed to get valid XML structure after {self._max_retries} attempts"
            if latest_error is None:
                raise ValueError(message)
            else:
                raise ValueError(message) from latest_error

        return xml_processor.fill(formatted_element)

    def _process_translated_element(self, root_element: Element) -> Element | None:
        found_any_visible_text = False

        for _, element in iter_with_stack(root_element):
            element.text = self._normalize_text(element.text)
            element.tail = self._normalize_text(element.tail)
            if self._is_visible_text(element.text):
                found_any_visible_text = True
            elif self._is_visible_text(element.tail) and element != root_element:
                found_any_visible_text = True

        if not found_any_visible_text:
            return None
        return root_element

    def _normalize_text(self, text: str | None) -> str | None:
        if text is None:
            return None
        return normalize_whitespace(text)

    def _is_visible_text(self, text: str | None) -> bool:
        return text is not None and bool(text.strip())
