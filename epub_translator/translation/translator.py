from xml.etree.ElementTree import Element

from ..llm import LLM, Message, MessageRole
from ..xml import encode_friendly, plain_text
from .format import ValidationError
from .xml_processor import XMLProcessor


class Translator:
    def __init__(self, llm: LLM) -> None:
        self._llm: LLM = llm

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
        max_retries = 5
        errors_limit = 10

        for _ in range(max_retries):
            response = self._llm.request(input=messages)
            try:
                return xml_processor.format(validated_text=response, errors_limit=errors_limit)

            except ValidationError as error:
                messages.append(Message(role=MessageRole.ASSISTANT, message=response))
                messages.append(Message(role=MessageRole.USER, message=str(error)))
                # print(f"  ✗ Validation error: {error}")

        raise RuntimeError(f"Failed to get valid XML structure after {max_retries} attempts")
