from collections.abc import Callable
from io import StringIO
from logging import Logger
from time import sleep
from typing import Any

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from .error import is_retry_error
from .increasable import Increasable, Increaser
from .types import Message, MessageRole


class LLMExecutor:
    def __init__(
        self,
        api_key: str,
        url: str,
        model: str,
        timeout: float | None,
        top_p: Increasable,
        temperature: Increasable,
        retry_times: int,
        retry_interval_seconds: float,
        create_logger: Callable[[], Logger | None],
    ) -> None:
        self._model_name: str = model
        self._timeout: float | None = timeout
        self._top_p: Increasable = top_p
        self._temperature: Increasable = temperature
        self._retry_times: int = retry_times
        self._retry_interval_seconds: float = retry_interval_seconds
        self._create_logger: Callable[[], Logger | None] = create_logger
        self._client = OpenAI(
            api_key=api_key,
            base_url=url,
            timeout=timeout,
        )

    def request(self, input: str | list[Message], parser: Callable[[str], Any], max_tokens: int | None) -> Any:
        result: Any | None = None
        last_error: Exception | None = None
        did_success = False
        top_p: Increaser = self._top_p.context()
        temperature: Increaser = self._temperature.context()
        logger = self._create_logger()

        if logger is not None:
            logger.debug(f"[[Request]]:\n{self._input2str(input)}\n")

        try:
            for i in range(self._retry_times + 1):
                try:
                    response = self._invoke_model(
                        input=input,
                        top_p=top_p.current,
                        temperature=temperature.current,
                        max_tokens=max_tokens,
                    )
                    if logger is not None:
                        logger.debug(f"[[Response]]:\n{response}\n")

                except Exception as err:
                    last_error = err
                    if not is_retry_error(err):
                        raise err
                    if logger is not None:
                        logger.warning(f"request failed with connection error, retrying... ({i + 1} times)")
                    if self._retry_interval_seconds > 0.0 and i < self._retry_times:
                        sleep(self._retry_interval_seconds)
                    continue

                try:
                    result = parser(response)
                    did_success = True
                    break

                except Exception as err:
                    last_error = err
                    warn_message = f"request failed with parsing error, retrying... ({i + 1} times)"
                    if logger is not None:
                        logger.warning(warn_message)
                    print(warn_message)
                    top_p.increase()
                    temperature.increase()
                    if self._retry_interval_seconds > 0.0 and i < self._retry_times:
                        sleep(self._retry_interval_seconds)
                    continue

        except KeyboardInterrupt as err:
            if last_error is not None and logger is not None:
                logger.debug(f"[[Error]]:\n{last_error}\n")
            raise err

        if not did_success:
            if last_error is None:
                raise RuntimeError("Request failed with unknown error")
            else:
                raise last_error

        return result

    def _input2str(self, input: str | list[Message]) -> str:
        if isinstance(input, str):
            return input
        if not isinstance(input, list):
            raise ValueError(f"Unsupported input type: {type(input)}")

        buffer = StringIO()
        is_first = True
        for message in input:
            if not is_first:
                buffer.write("\n\n")
            if message.role == MessageRole.SYSTEM:
                buffer.write("System:\n")
                buffer.write(message.message)
            elif message.role == MessageRole.USER:
                buffer.write("User:\n")
                buffer.write(message.message)
            elif message.role == MessageRole.ASSISTANT:
                buffer.write("Assistant:\n")
                buffer.write(message.message)
            else:
                buffer.write(str(message))
            is_first = False

        return buffer.getvalue()

    def _invoke_model(
        self,
        input: str | list[Message],
        top_p: float | None,
        temperature: float | None,
        max_tokens: int | None,
    ):
        if isinstance(input, str):
            input = [Message(role=MessageRole.USER, message=input)]

        messages: list[ChatCompletionMessageParam] = []
        for message in input:
            if message.role == MessageRole.SYSTEM:
                messages.append(
                    {
                        "role": "system",
                        "content": message.message,
                    }
                )
            elif message.role == MessageRole.USER:
                messages.append(
                    {
                        "role": "user",
                        "content": message.message,
                    }
                )
            elif message.role == MessageRole.ASSISTANT:
                messages.append(
                    {
                        "role": "assistant",
                        "content": message.message,
                    }
                )

        stream = self._client.chat.completions.create(
            model=self._model_name,
            messages=messages,
            stream=True,
            top_p=top_p,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        buffer = StringIO()
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                buffer.write(chunk.choices[0].delta.content)
        return buffer.getvalue()
