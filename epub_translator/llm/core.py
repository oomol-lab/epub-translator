import datetime
from collections.abc import Generator
from importlib.resources import files
from logging import DEBUG, FileHandler, Formatter, Logger, getLogger
from os import PathLike
from pathlib import Path

from jinja2 import Environment, Template
from tiktoken import Encoding, get_encoding

from ..template import create_env
from .context import LLMContext
from .executor import LLMExecutor
from .increasable import Increasable
from .types import Message


class LLM:
    def __init__(
        self,
        key: str,
        url: str,
        model: str,
        token_encoding: str,
        timeout: float | None = None,
        top_p: float | tuple[float, float] | None = None,
        temperature: float | tuple[float, float] | None = None,
        retry_times: int = 5,
        retry_interval_seconds: float = 6.0,
        cache_path: PathLike | str | None = None,
        log_dir_path: PathLike | str | None = None,
    ) -> None:
        prompts_path = Path(str(files("epub_translator"))) / "data"
        self._templates: dict[str, Template] = {}
        self._encoding: Encoding = get_encoding(token_encoding)
        self._env: Environment = create_env(prompts_path)
        self._top_p: Increasable = Increasable(top_p)
        self._temperature: Increasable = Increasable(temperature)
        self._cache_path: Path | None = self._ensure_dir_path(cache_path)
        self._logger_save_path: Path | None = self._ensure_dir_path(log_dir_path)

        self._executor = LLMExecutor(
            url=url,
            model=model,
            api_key=key,
            timeout=timeout,
            retry_times=retry_times,
            retry_interval_seconds=retry_interval_seconds,
            create_logger=self._create_logger,
        )

    @property
    def encoding(self) -> Encoding:
        return self._encoding

    def context(self, cache_seed_content: str | None = None) -> LLMContext:
        return LLMContext(
            executor=self._executor,
            cache_path=self._cache_path,
            cache_seed_content=cache_seed_content,
            top_p=self._top_p,
            temperature=self._temperature,
        )

    def request(
        self,
        input: str | list[Message],
        max_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
    ) -> str:
        with self.context() as ctx:
            return ctx.request(
                input=input,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
            )

    def template(self, template_name: str) -> Template:
        template = self._templates.get(template_name, None)
        if template is None:
            template = self._env.get_template(template_name)
            self._templates[template_name] = template
        return template

    def _ensure_dir_path(self, path: PathLike | str | None) -> Path | None:
        if path is None:
            return None
        dir_path = Path(path)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
        elif not dir_path.is_dir():
            return None
        return dir_path.resolve()

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
