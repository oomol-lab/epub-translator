from collections.abc import Callable
from xml.etree.ElementTree import Element

from ..llm import LLM
from ..llm.types import Message, MessageRole
from ..xml import encode_friendly
from .format import ValidationError, format


class Filler:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm

    def fill(self, source_ele: Element, translated_text: str, on_fail: Callable[[str], None] | None = None) -> Element:
        # Load template and create system prompt
        template = self.llm._template("fill")
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
            # Call LLM to get response
            response = self._call_llm(messages)

            # Try to validate and extract XML
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

    def _call_llm(self, messages: list[Message]) -> str:
        # Convert messages to OpenAI format and call the client
        client = self.llm._executor._client
        model_name = self.llm._executor._model_name

        openai_messages = [
            {
                "role": self._role_to_str(msg.role),
                "content": msg.message,
            }
            for msg in messages
        ]

        response = client.chat.completions.create(
            model=model_name,
            messages=openai_messages,
        )
        return response.choices[0].message.content or ""

    def _role_to_str(self, role: MessageRole) -> str:
        if role == MessageRole.SYSTEM:
            return "system"
        elif role == MessageRole.USER:
            return "user"
        elif role == MessageRole.ASSISTANT:
            return "assistant"
        else:
            raise ValueError(f"Unknown role: {role}")
