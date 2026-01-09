from collections.abc import Iterator
from typing import Generic, TypeVar, cast

T = TypeVar("T")


class Peakable(Generic[T], Iterator[T]):
    def __init__(self, iterator: Iterator[T]) -> None:
        self._iterator = iterator
        self._buffer: T | None = None
        self._has_buffer = False

    @property
    def has_next(self) -> bool:
        if self._has_buffer:
            return True
        try:
            self._buffer = next(self._iterator)
            self._has_buffer = True
            return True
        except StopIteration:
            return False

    def peak(self) -> T:
        if not self._has_buffer:
            self._buffer = next(self._iterator)
            self._has_buffer = True
        return cast(T, self._buffer)

    def __iter__(self):
        return self

    def __next__(self) -> T:
        if self._has_buffer:
            buffer = self._buffer
            self._buffer = None
            self._has_buffer = False
            return cast(T, buffer)
        return next(self._iterator)
