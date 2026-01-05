from collections.abc import Iterable

from ..segment import BlockError, FoundInvalidIDError, InlineError


def validate(errors: Iterable[BlockError | InlineError | FoundInvalidIDError]):
    for error in errors:
        pass
