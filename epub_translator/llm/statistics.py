from threading import Lock

from openai.types import CompletionUsage


class Statistics:
    def __init__(self) -> None:
        self._lock = Lock()
        self.total_tokens = 0
        self.input_tokens = 0
        self.input_cache_tokens = 0
        self.output_tokens = 0

    def submit_usage(self, usage: CompletionUsage | None) -> None:
        if usage is None:
            return
        with self._lock:
            if usage.total_tokens:
                self.total_tokens += usage.total_tokens
            if usage.prompt_tokens:
                self.input_tokens += usage.prompt_tokens
            if usage.prompt_tokens_details and usage.prompt_tokens_details.cached_tokens:
                self.input_cache_tokens += usage.prompt_tokens_details.cached_tokens
            if usage.completion_tokens:
                self.output_tokens += usage.completion_tokens
