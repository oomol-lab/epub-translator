from collections.abc import Callable
from xml.etree.ElementTree import Element

from ..llm import LLM, Message, MessageRole
from ..xml import encode_friendly
from .format import ValidationError, format


class Filler:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm

    def fill(self, source_ele: Element, translated_text: str, on_fail: Callable[[str], None] | None = None) -> Element:
        # Load template and create system prompt
        template = self.llm.template("fill")
        system_prompt = template.render()

        # Create initial messages
        source_xml = encode_friendly(source_ele)
        user_content = f"```XML\n{source_xml}\n```\n\n{translated_text}"

        messages: list[Message] = [
            Message(role=MessageRole.SYSTEM, message=system_prompt),
            Message(role=MessageRole.USER, message=user_content),
        ]

        # Retry loop with validation feedback
        max_retries = 5
        errors_limit = 10

        for _ in range(max_retries):
            response = self.llm.request(input=messages)
            try:
                return format(
                    template_ele=source_ele,
                    validated_text=response,
                    errors_limit=errors_limit,
                )
            except ValidationError as e:
                # Add error feedback to conversation and retry
                messages.append(Message(role=MessageRole.ASSISTANT, message=response))
                messages.append(Message(role=MessageRole.USER, message=str(e)))
                if on_fail:
                    on_fail(str(e))

        # If all retries failed
        raise RuntimeError(f"Failed to get valid XML structure after {max_retries} attempts")
