from collections.abc import Generator, Iterable
from typing import Generic, TypeVar

T = TypeVar("T")


class IterSync(Generic[T]):
    def __init__(self) -> None:
        super().__init__()
        self._queue: list[T] = []

    @property
    def tail(self) -> T | None:
        if not self._queue:
            return None
        return self._queue[-1]

    def take(self) -> T:
        return self._queue.pop()

    def iter(self, elements: Iterable[T]) -> Generator[T, None, None]:
        for element in elements:
            self._queue.insert(0, element)
            yield element
