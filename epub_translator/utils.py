import re
from collections.abc import Iterable
from typing import TypeVar

T = TypeVar("T")

_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_whitespace(text: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", text)


def is_the_same(elements: Iterable[T]) -> bool:
    iterator = iter(elements)
    try:
        first_element = next(iterator)
    except StopIteration:
        return True

    for element in iterator:
        if element != first_element:
            return False
    return True
