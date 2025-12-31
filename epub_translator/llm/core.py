import datetime
import hashlib
import json
import uuid
from collections.abc import Callable, Generator
from importlib.resources import files
from logging import DEBUG, FileHandler, Formatter, Logger, getLogger
from os import PathLike
from pathlib import Path
from typing import Self

from jinja2 import Environment, Template
from tiktoken import Encoding, get_encoding

from ..template import create_env
from .executor import LLMExecutor
from .increasable import Increasable
from .types import Message, MessageRole, R


class LLMContext:
    """Context manager for LLM requests with transactional caching."""

    def __init__(
        self,
        executor: LLMExecutor,
        cache_path: Path | None,
    ) -> None:
        self._executor = executor
        self._cache_path = cache_path
        self._context_id = uuid.uuid4().hex[:12]
        self._temp_files: list[Path] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None:
            # Success: commit all temporary cache files
            self._commit()
        else:
            # Failure: rollback (delete) all temporary cache files
            self._rollback()

    def request(
        self,
        input: str | list[Message],
        parser: Callable[[str], R] = lambda x: x,
        max_tokens: int | None = None,
    ) -> R:
        messages: list[Message]
        if isinstance(input, str):
            messages = [Message(role=MessageRole.USER, message=input)]
        else:
            messages = input

        cache_key: str | None = None
        if self._cache_path is not None:
            cache_key = self._compute_messages_hash(messages)
            permanent_cache_file = self._cache_path / f"{cache_key}.txt"
            if permanent_cache_file.exists():
                cached_content = permanent_cache_file.read_text(encoding="utf-8")
                return parser(cached_content)

            temp_cache_file = self._cache_path / f"{cache_key}.{self._context_id}.txt"
            if temp_cache_file.exists():
                cached_content = temp_cache_file.read_text(encoding="utf-8")
                return parser(cached_content)

        # Make the actual request
        response = self._executor.request(
            messages=messages,
            parser=lambda x: x,
            max_tokens=max_tokens,
        )

        # Save to temporary cache if cache_path is set
        if self._cache_path is not None and cache_key is not None:
            temp_cache_file = self._cache_path / f"{cache_key}.{self._context_id}.txt"
            temp_cache_file.write_text(response, encoding="utf-8")
            self._temp_files.append(temp_cache_file)

        return parser(response)

    def _compute_messages_hash(self, messages: list[Message]) -> str:
        messages_dict = [{"role": msg.role.value, "message": msg.message} for msg in messages]
        messages_json = json.dumps(messages_dict, ensure_ascii=False, sort_keys=True)
        return hashlib.sha512(messages_json.encode("utf-8")).hexdigest()

    def _commit(self) -> None:
        for temp_file in self._temp_files:
            if temp_file.exists():
                # Remove the .[context-id].txt suffix to get permanent name
                permanent_name = temp_file.name.rsplit(".", 2)[0] + ".txt"
                permanent_file = temp_file.parent / permanent_name
                temp_file.rename(permanent_file)

    def _rollback(self) -> None:
        for temp_file in self._temp_files:
            if temp_file.exists():
                temp_file.unlink()


class LLM:
    def __init__(
        self,
        key: str,
        url: str,
        model: str,
        token_encoding: str,
        cache_path: PathLike | None = None,
        timeout: float | None = None,
        top_p: float | tuple[float, float] | None = None,
        temperature: float | tuple[float, float] | None = None,
        retry_times: int = 5,
        retry_interval_seconds: float = 6.0,
        log_dir_path: PathLike | None = None,
    ) -> None:
        prompts_path = Path(str(files("epub_translator"))) / "data"
        self._templates: dict[str, Template] = {}
        self._encoding: Encoding = get_encoding(token_encoding)
        self._env: Environment = create_env(prompts_path)
        self._logger_save_path: Path | None = None
        self._cache_path: Path | None = None

        if cache_path is not None:
            self._cache_path = Path(cache_path)
            if not self._cache_path.exists():
                self._cache_path.mkdir(parents=True, exist_ok=True)
            elif not self._cache_path.is_dir():
                self._cache_path = None

        if log_dir_path is not None:
            self._logger_save_path = Path(log_dir_path)
            if not self._logger_save_path.exists():
                self._logger_save_path.mkdir(parents=True, exist_ok=True)
            elif not self._logger_save_path.is_dir():
                self._logger_save_path = None

        self._executor = LLMExecutor(
            url=url,
            model=model,
            api_key=key,
            timeout=timeout,
            top_p=Increasable(top_p),
            temperature=Increasable(temperature),
            retry_times=retry_times,
            retry_interval_seconds=retry_interval_seconds,
            create_logger=self._create_logger,
        )

    @property
    def encoding(self) -> Encoding:
        return self._encoding

    def context(self) -> LLMContext:
        return LLMContext(
            executor=self._executor,
            cache_path=self._cache_path,
        )

    def request(
        self,
        input: str | list[Message],
        parser: Callable[[str], R] = lambda x: x,
        max_tokens: int | None = None,
    ) -> R:
        with self.context() as ctx:
            return ctx.request(input=input, parser=parser, max_tokens=max_tokens)

    def template(self, template_name: str) -> Template:
        template = self._templates.get(template_name, None)
        if template is None:
            template = self._env.get_template(template_name)
            self._templates[template_name] = template
        return template

    def _create_logger(self) -> Logger | None:
        if self._logger_save_path is None:
            return None

        now = datetime.datetime.now(datetime.UTC)
        timestamp = now.strftime("%Y-%m-%d %H-%M-%S %f")
        file_path = self._logger_save_path / f"request {timestamp}.log"
        logger = getLogger(f"LLM Request {timestamp}")
        logger.setLevel(DEBUG)
        handler = FileHandler(file_path, encoding="utf-8")
        handler.setLevel(DEBUG)
        handler.setFormatter(Formatter("%(asctime)s    %(message)s", "%H:%M:%S"))
        logger.addHandler(handler)

        return logger

    def _search_quotes(self, kind: str, response: str) -> Generator[str, None, None]:
        start_marker = f"```{kind}"
        end_marker = "```"
        start_index = 0

        while True:
            start_index = self._find_ignore_case(
                raw=response,
                sub=start_marker,
                start=start_index,
            )
            if start_index == -1:
                break

            end_index = self._find_ignore_case(
                raw=response,
                sub=end_marker,
                start=start_index + len(start_marker),
            )
            if end_index == -1:
                break

            extracted_text = response[start_index + len(start_marker) : end_index].strip()
            yield extracted_text
            start_index = end_index + len(end_marker)

    def _find_ignore_case(self, raw: str, sub: str, start: int = 0):
        if not sub:
            return 0 if 0 >= start else -1

        raw_len, sub_len = len(raw), len(sub)
        for i in range(start, raw_len - sub_len + 1):
            match = True
            for j in range(sub_len):
                if raw[i + j].lower() != sub[j].lower():
                    match = False
                    break
            if match:
                return i
        return -1
