from xml.etree.ElementTree import Element

from ..llm import LLM, Message, MessageRole
from ..xml import encode_friendly
from .format import ValidationError, format


class Translator:
    def __init__(self, llm: LLM) -> None:
        self._llm: LLM = llm

    def translate(self, text: str, element: Element) -> Element:
        translated_text = self._translate_text(text)
        translated_element = self._fill(element, translated_text)
        return translated_element

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

    def _fill(self, source_ele: Element, translated_text: str) -> Element:
        messages: list[Message] = [
            Message(
                role=MessageRole.SYSTEM,
                message=self._llm.template("fill").render(),
            ),
            Message(
                role=MessageRole.USER,
                message=f"```XML\n{encode_friendly(source_ele)}\n```\n\n{translated_text}",
            ),
        ]
        max_retries = 5
        errors_limit = 10

        for _ in range(max_retries):
            response = self._llm.request(input=messages)
            try:
                return format(
                    template_ele=source_ele,
                    validated_text=response,
                    errors_limit=errors_limit,
                )
            except ValidationError as error:
                messages.append(Message(role=MessageRole.ASSISTANT, message=response))
                messages.append(Message(role=MessageRole.USER, message=str(error)))
                # print(f"  ✗ Validation error: {error}")

        raise RuntimeError(f"Failed to get valid XML structure after {max_retries} attempts")
