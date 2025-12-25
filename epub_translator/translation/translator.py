from xml.etree.ElementTree import Element

from ..llm import LLM, Message, MessageRole
from ..xml import encode_friendly, plain_text
from .format import ValidationError, format
from .xml_processor import XMLProcessor


class Translator:
    def __init__(
        self,
        llm: LLM,
        ignore_translated_error: bool,
        max_retries: int,
        max_fill_displaying_errors: int,
    ) -> None:
        self._llm: LLM = llm
        self._ignore_translated_error: bool = ignore_translated_error
        self._max_retries: int = max_retries
        self._max_fill_displaying_errors: int = max_fill_displaying_errors

    def translate(self, element: Element) -> Element | None:
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
                    message=self._llm.template("translate").render(),
                ),
                Message(role=MessageRole.USER, message=text),
            ]
        )

    def _fill_into_xml(self, xml_processor: XMLProcessor, translated_text: str) -> Element | None:
        processed = xml_processor.processed
        assert processed is not None
        messages: list[Message] = [
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
            response = self._llm.request(input=messages)
            try:
                formatted_element = format(
                    template_ele=processed,
                    validated_text=response,
                    errors_limit=self._max_fill_displaying_errors,
                )
            except ValidationError as error:
                latest_error = error
                if self._ignore_translated_error and error.validated_ele is not None:
                    formatted_element = error.validated_ele
                messages.append(Message(role=MessageRole.ASSISTANT, message=response))
                messages.append(Message(role=MessageRole.USER, message=str(error)))
                # print(f"  ✗ Validation error: {error}")

        if formatted_element is None:
            message = f"Failed to get valid XML structure after {self._max_retries} attempts"
            if latest_error is None:
                raise ValueError(message)
            else:
                raise ValueError(message) from latest_error

        return xml_processor.fill(formatted_element)
