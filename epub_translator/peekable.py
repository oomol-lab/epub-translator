from collections.abc import Iterator
from typing import Generic, TypeVar, cast

T = TypeVar("T")

_MISSING = object()


class Peekable(Generic[T]):
    def __init__(self, iterator: Iterator[T]) -> None:
        self._iterator: Iterator[T] = iterator
        self._peeked: T = cast(T, _MISSING)

    def peek(self) -> T:
        if self._peeked is _MISSING:
            self._peeked = next(self._iterator)
        return self._peeked

    def __iter__(self) -> "Peekable[T]":
        return self

    def __next__(self) -> T:
        if self._peeked is not _MISSING:
            value = self._peeked
            self._peeked = cast(T, _MISSING)
            return value
        return next(self._iterator)
