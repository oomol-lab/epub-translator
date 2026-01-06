from collections.abc import Callable
from io import StringIO
from logging import Logger
from time import sleep
from typing import cast

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from .error import is_retry_error
from .increasable import Increasable, Increaser
from .types import Message, MessageRole, R


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

    def request(
        self,
        messages: list[Message],
        parser: Callable[[str], R],
        max_tokens: int | None,
        temperature: float | None = None,
        top_p: float | None = None,
    ) -> R:
        result: R | None = None
        last_error: Exception | None = None
        did_success = False

        # 确定是否使用固定参数（用户传入的覆盖值）
        use_fixed_temperature = temperature is not None
        use_fixed_top_p = top_p is not None

        # 初始化 increaser（只在非固定时使用，重试失败时自动调整）
        top_p_increaser: Increaser = self._top_p.context()
        temperature_increaser: Increaser = self._temperature.context()

        logger = self._create_logger()

        if logger is not None:
            logger.debug(f"[[Request]]:\n{self._input2str(messages)}\n")

        try:
            for i in range(self._retry_times + 1):
                # 确定本次请求使用的参数（固定值或当前 increaser 值）
                final_top_p = top_p if use_fixed_top_p else top_p_increaser.current
                final_temperature = temperature if use_fixed_temperature else temperature_increaser.current

                try:
                    response = self._invoke_model(
                        input_messages=messages,
                        top_p=final_top_p,
                        temperature=final_temperature,
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

                    # 只在非固定参数时增加参数值（固定参数不应该在重试时变化）
                    if not use_fixed_top_p:
                        top_p_increaser.increase()
                    if not use_fixed_temperature:
                        temperature_increaser.increase()

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

        return cast(R, result)

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
        input_messages: list[Message],
        top_p: float | None,
        temperature: float | None,
        max_tokens: int | None,
    ):
        messages: list[ChatCompletionMessageParam] = []
        for item in input_messages:
            if item.role == MessageRole.SYSTEM:
                messages.append(
                    {
                        "role": "system",
                        "content": item.message,
                    }
                )
            elif item.role == MessageRole.USER:
                messages.append(
                    {
                        "role": "user",
                        "content": item.message,
                    }
                )
            elif item.role == MessageRole.ASSISTANT:
                messages.append(
                    {
                        "role": "assistant",
                        "content": item.message,
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
