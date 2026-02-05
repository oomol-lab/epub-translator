from threading import Lock


class LLMStatistics:
    """Token usage statistics for LLM."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.total_tokens = 0
        self.input_tokens = 0
        self.input_cache_tokens = 0
        self.output_tokens = 0
        self.output_cache_tokens = 0

    def update_from_usage(self, usage) -> None:
        """Update statistics from OpenAI usage object."""
        with self._lock:
            if hasattr(usage, "total_tokens") and usage.total_tokens:
                self.total_tokens += usage.total_tokens
            if hasattr(usage, "prompt_tokens") and usage.prompt_tokens:
                self.input_tokens += usage.prompt_tokens
            if hasattr(usage, "prompt_tokens_details") and usage.prompt_tokens_details:
                if hasattr(usage.prompt_tokens_details, "cached_tokens") and usage.prompt_tokens_details.cached_tokens:
                    self.input_cache_tokens += usage.prompt_tokens_details.cached_tokens
            if hasattr(usage, "completion_tokens") and usage.completion_tokens:
                self.output_tokens += usage.completion_tokens
            if hasattr(usage, "completion_tokens_details") and usage.completion_tokens_details:
                if (
                    hasattr(usage.completion_tokens_details, "cached_tokens")
                    and usage.completion_tokens_details.cached_tokens
                ):
                    self.output_cache_tokens += usage.completion_tokens_details.cached_tokens
