from collections.abc import Callable, Iterable
from dataclasses import dataclass

from ..segment import TextSegment


@dataclass
class FillFailedEvent:
    error_message: str
    retried_count: int
    over_maximum_retries: int


@dataclass
class Callbacks:
    interrupt_source_text_segments: Callable[[TextSegment], Iterable[TextSegment]]
    interrupt_translated_text_segments: Callable[[TextSegment], Iterable[TextSegment]]
    on_fill_failed: Callable[[FillFailedEvent], None]


def warp_callbacks(
    interrupt_source_text_segments: Callable[[TextSegment], Iterable[TextSegment]] | None,
    interrupt_translated_text_segments: Callable[[TextSegment], Iterable[TextSegment]] | None,
    on_fill_failed: Callable[[FillFailedEvent], None] | None,
) -> Callbacks:
    return Callbacks(
        interrupt_source_text_segments=interrupt_source_text_segments or (lambda segment: (segment,)),
        interrupt_translated_text_segments=interrupt_translated_text_segments or (lambda segment: (segment,)),
        on_fill_failed=on_fill_failed or (lambda event: None),
    )
