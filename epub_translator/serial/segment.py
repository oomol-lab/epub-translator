from collections.abc import Callable, Iterable
from typing import Generic, Protocol, Self, TypeVar, runtime_checkable

S = TypeVar("S")
T = TypeVar("T")
ST = TypeVar("ST", bound="Segment")


@runtime_checkable
class Segment(Protocol, Generic[S]):
    tokens: int
    payload: S

    def truncate_after_head(self, remain_tokens: int) -> Self: ...
    def truncate_before_tail(self, remain_tokens: int) -> Self: ...


def split(
    segments: Iterable[ST],
    transform: Callable[[list[ST]], list[T]],
    max_group_tokens: int,
) -> Iterable[T]:
    raise NotImplementedError()
