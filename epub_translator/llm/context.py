import hashlib
import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Self

from .executor import LLMExecutor
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
        temperature: float | None = None,
        top_p: float | None = None,
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
            temperature=temperature,
            top_p=top_p,
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
