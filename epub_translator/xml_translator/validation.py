from collections.abc import Generator, Iterable
from dataclasses import dataclass
from typing import Generic, TypeVar, cast
from xml.etree.ElementTree import Element

from ..segment import (
    BlockContentError,
    BlockError,
    BlockExpectedIDsError,
    BlockUnexpectedIDError,
    BlockWrongTagError,
    FoundInvalidIDError,
    InlineError,
    InlineExpectedIDsError,
    InlineLostIDError,
    InlineUnexpectedIDError,
    InlineWrongTagCountError,
)
from ..utils import ensure_list

_LEVEL_WEIGHT = 3

_BLOCK_WRONG_TAG_LEVEL = 5
_BLOCK_EXPECTED_IDS_LEVEL = 5
_BLOCK_FOUND_INVALID_ID_LEVEL = 4
_BLOCK_UNEXPECTED_ID_LEVEL = 3

_INLINE_LOST_ID_LEVEL = 2
_INLINE_EXPECTED_IDS_LEVEL = 2
_INLINE_FOUND_INVALID_ID_LEVEL = 1
_INLINE_WRONG_TAG_COUNT_LEVEL = 0
_INLINE_UNEXPECTED_ID_LEVEL = 0


@dataclass
class _BlockErrorInfo:
    error: BlockError | FoundInvalidIDError
    level: int
    weight: int


@dataclass
class _InlineErrorInfo:
    error: InlineError | FoundInvalidIDError
    level: int
    weight: int


@dataclass
class _ErrorGroup:
    block: tuple[int, Element] | None  # (block_id, block_element)
    block_errors: list[_BlockErrorInfo]
    inline_errors: list[_InlineErrorInfo]
    total_score: int


ERROR = TypeVar("ERROR")


@dataclass
class ValidationReporting:
    error_message: str | None
    block_score: int
    inline_scores: dict[int, int]


def validate(
    errors: Iterable[BlockError | FoundInvalidIDError],
    max_errors: int,
) -> ValidationReporting:
    error_groups = _collect_and_group_errors(errors)
    block_score: int = 0
    inline_scores: dict[int, int] = {}

    if None in error_groups:
        block_score = sum(e.weight for e in error_groups[None].block_errors)
    for block_id, group in error_groups.items():
        if block_id is not None and group.inline_errors:
            inline_scores[block_id] = sum(e.weight for e in group.inline_errors)

    return ValidationReporting(
        block_score=block_score,
        inline_scores=inline_scores,
        error_message=_build_error_message(
            error_groups=error_groups,
            max_errors=max_errors,
        ),
    )


@dataclass
class ErrorItem(Generic[ERROR]):
    error: ERROR
    index1: int
    index2: int
    level: int
    weight: int


@dataclass
class BlockErrorsGroup:
    weight: int
    block_id: int
    block_element: Element
    errors: list[ErrorItem[BlockError | FoundInvalidIDError] | ErrorItem[InlineError | FoundInvalidIDError]]


@dataclass
class ErrorsGroup:
    upper_errors: list[ErrorItem[BlockError | FoundInvalidIDError]]
    block_groups: list[BlockErrorsGroup]

    @property
    def errors_count(self) -> int:
        count = len(self.upper_errors)
        for block_group in self.block_groups:
            count += len(block_group.errors)
        return count


def nest_as_errors_group(errors: Iterable[BlockError | FoundInvalidIDError]) -> ErrorsGroup | None:
    return _create_errors_group(
        error_items=_transform_errors_to_items(errors),
    )


def truncate_errors_group(errors_group: ErrorsGroup, max_errors: int) -> ErrorsGroup | None:
    errors_items = list(_flatten_errors_group(errors_group))
    if len(errors_items) <= max_errors:
        return errors_group

    errors_items.sort(key=lambda item: (-item[1].weight, item[1].index1, item[1].index2))
    errors_items = errors_items[:max_errors]
    return _create_errors_group(errors_items)


@dataclass
class _Block:
    id: int
    element: Element


def _transform_errors_to_items(errors: Iterable[BlockError | FoundInvalidIDError]):
    for i, block_error in enumerate(errors):
        if isinstance(block_error, BlockContentError):
            block = _Block(
                id=block_error.id,
                element=block_error.element,
            )
            for j, inline_error in enumerate(block_error.errors):
                level = _get_inline_error_level(inline_error)
                weight = _calculate_error_weight(inline_error, level)
                yield (
                    block,
                    ErrorItem(
                        error=inline_error,
                        index1=i,
                        index2=j,
                        level=level,
                        weight=weight,
                    ),
                )
        else:
            level = _get_block_error_level(block_error)
            weight = _calculate_error_weight(block_error, level)
            error_item: ErrorItem[BlockError | FoundInvalidIDError] = ErrorItem(
                error=block_error,
                index1=i,
                index2=0,
                level=level,
                weight=weight,
            )
            block: _Block | None = None
            if isinstance(block_error, BlockWrongTagError) and block_error.block is not None:
                block = _Block(
                    id=block_error.block[0],
                    element=block_error.block[1],
                )
            yield block, error_item


def _flatten_errors_group(
    errors_group: ErrorsGroup,
) -> Generator[
    tuple[
        _Block | None,
        ErrorItem[BlockError | FoundInvalidIDError] | ErrorItem[InlineError | FoundInvalidIDError],
    ],
    None,
    None,
]:
    for error in errors_group.upper_errors:
        yield None, error

    for block_group in errors_group.block_groups:
        block = _Block(
            id=block_group.block_id,
            element=block_group.block_element,
        )
        for error in block_group.errors:
            yield block, error


def _create_errors_group(
    error_items: Iterable[
        tuple[
            _Block | None,
            ErrorItem[BlockError | FoundInvalidIDError] | ErrorItem[InlineError | FoundInvalidIDError],
        ]
    ],
) -> ErrorsGroup | None:
    upper_errors: list[ErrorItem[BlockError | FoundInvalidIDError]] = []
    block_elements: dict[int, Element] = {}
    block_errors_dict: dict[
        int, list[ErrorItem[BlockError | FoundInvalidIDError] | ErrorItem[InlineError | FoundInvalidIDError]]
    ] = {}

    for block, error in error_items:
        if block is None:
            upper_errors.append(cast(ErrorItem[BlockError | FoundInvalidIDError], error))
        else:
            block_errors = ensure_list(block_errors_dict, block.id)
            block_errors.append(error)
            block_elements[block.id] = block.element

    if not upper_errors and not block_errors_dict:
        return None

    block_errors_groups: list[BlockErrorsGroup] = []
    for block_id, block_errors in block_errors_dict.items():
        block_element = block_elements.get(block_id)
        if block_element is None:
            continue

        block_error_group = BlockErrorsGroup(
            weight=sum(e.weight for e in block_errors),
            block_id=block_id,
            block_element=block_element,
            errors=sorted(block_errors, key=lambda e: (-e.weight, e.index1, e.index2)),
        )
        block_errors_groups.append(block_error_group)

    block_errors_groups.sort(key=lambda g: -g.weight)
    upper_errors.sort(key=lambda e: (-e.weight, e.index1, e.index2))

    return ErrorsGroup(
        upper_errors=upper_errors,
        block_groups=block_errors_groups,
    )


def _collect_and_group_errors(
    errors: Iterable[BlockError | FoundInvalidIDError],
) -> dict[int | None, _ErrorGroup]:
    error_groups: dict[int | None, _ErrorGroup] = {}

    for error in errors:
        if isinstance(error, BlockContentError):
            block_id = error.id
            if block_id not in error_groups:
                error_groups[block_id] = _ErrorGroup(
                    block=(block_id, error.element),
                    block_errors=[],
                    inline_errors=[],
                    total_score=0,
                )
            for inline_error in error.errors:
                level = _get_inline_error_level(inline_error)
                weight = _calculate_error_weight(inline_error, level)
                error_groups[block_id].inline_errors.append(
                    _InlineErrorInfo(error=inline_error, level=level, weight=weight)
                )
        else:
            if None not in error_groups:
                error_groups[None] = _ErrorGroup(
                    block=None,
                    block_errors=[],
                    inline_errors=[],
                    total_score=0,
                )
            level = _get_block_error_level(error)
            weight = _calculate_error_weight(error, level)
            error_groups[None].block_errors.append(_BlockErrorInfo(error=error, level=level, weight=weight))

    for group in error_groups.values():
        group.block_errors.sort(key=lambda e: -e.level)
        group.inline_errors.sort(key=lambda e: -e.level)
        group.total_score = sum(e.weight for e in group.block_errors) + sum(e.weight for e in group.inline_errors)

    return error_groups


def error_message(errors_group: ErrorsGroup | None, omitted_count: int = 0):
    if errors_group is None:
        return None

    message_lines: list[str] = []
    for upper_error in errors_group.upper_errors:
        message_lines.append(_format_block_error(upper_error.error))
    if message_lines:
        message_lines.append("")

    for block_group in errors_group.block_groups:
        # TODO: 添加一句承上启下的话，表明接下来都局限于某个 block 内
        for block_error in block_group.errors:
            message: str
            if isinstance(block_error.error, BlockError):
                message = _format_block_error(block_error.error)
            elif isinstance(block_error.error, InlineError):
                message = _format_inline_error(block_error.error, block_group.block_id)
            else:
                raise RuntimeError()
            message_lines.append(message)
        message_lines.append("")

    if not message_lines:
        return None

    message_lines.insert(0, f"Found {errors_group.errors_count} error(s) in total. Fix them and submit again:\n")
    if omitted_count > 0:
        message_lines.append(f"\n... and {omitted_count} more error(s) omitted.")

    return "\n".join(message_lines)


def _build_error_message(
    error_groups: dict[int | None, _ErrorGroup],
    max_errors: int,
) -> str | None:
    if not error_groups:
        return None

    total_error_count = sum(len(g.block_errors) + len(g.inline_errors) for g in error_groups.values())
    if total_error_count == 0:
        return None

    messages: list[str] = []
    shown_error_count = 0
    for group in sorted(error_groups.values(), key=lambda g: -g.total_score):
        if shown_error_count >= max_errors:
            break

        group_messages: list[str] = []
        for error_info in group.block_errors:
            if shown_error_count >= max_errors:
                break
            group_messages.append(_format_block_error(error_info.error))
            shown_error_count += 1

        inline_messages: list[str] = []
        if group.block is not None:  # inline 错误必须有 block_id
            for error_info in group.inline_errors:
                if shown_error_count >= max_errors:
                    break
                block_id, _ = group.block
                inline_messages.append(_format_inline_error(error_info.error, block_id))
                shown_error_count += 1

        if inline_messages:
            group_messages.extend(f"  - {msg}" for msg in inline_messages)

        if group_messages:
            if group.block is not None:
                # 从 parent element 中获取 block_tag
                block_id, block_element = group.block
                messages.append(f"In {block_element.tag}#{block_id}:\n" + "\n".join(group_messages))
            else:
                messages.extend(group_messages)

    if not messages:
        return None

    header = f"Found {total_error_count} error(s) in total:"
    result = header + "\n\n" + "\n\n".join(messages)
    if shown_error_count < total_error_count:
        omitted_count = total_error_count - shown_error_count
        result += f"\n\n... and {omitted_count} more error(s) omitted."

    return result


def _calculate_error_weight(error: BlockError | InlineError | FoundInvalidIDError, level: int) -> int:
    # BlockExpectedIDsError 和 InlineExpectedIDsError 的权重乘以 id2element 数量
    if isinstance(error, (BlockExpectedIDsError, InlineExpectedIDsError)):
        return (_LEVEL_WEIGHT**level) * len(error.id2element)
    else:
        return _LEVEL_WEIGHT**level


def _get_block_error_level(error: BlockError | FoundInvalidIDError) -> int:
    if isinstance(error, BlockWrongTagError):
        return _BLOCK_WRONG_TAG_LEVEL
    elif isinstance(error, BlockExpectedIDsError):
        return _BLOCK_EXPECTED_IDS_LEVEL
    elif isinstance(error, BlockUnexpectedIDError):
        return _BLOCK_UNEXPECTED_ID_LEVEL
    elif isinstance(error, FoundInvalidIDError):
        return _BLOCK_FOUND_INVALID_ID_LEVEL
    else:
        return 0


def _get_inline_error_level(error: InlineError | FoundInvalidIDError) -> int:
    if isinstance(error, InlineLostIDError):
        return _INLINE_LOST_ID_LEVEL
    elif isinstance(error, InlineExpectedIDsError):
        return _INLINE_EXPECTED_IDS_LEVEL
    elif isinstance(error, InlineUnexpectedIDError):
        return _INLINE_UNEXPECTED_ID_LEVEL
    elif isinstance(error, InlineWrongTagCountError):
        return _INLINE_WRONG_TAG_COUNT_LEVEL
    elif isinstance(error, FoundInvalidIDError):
        return _INLINE_FOUND_INVALID_ID_LEVEL
    else:
        return 0


def _format_block_error(error: BlockError | FoundInvalidIDError) -> str:
    if isinstance(error, BlockWrongTagError):
        if error.block is None:
            return (
                f"Root tag mismatch: expected `<{error.expected_tag}>`, but found `<{error.instead_tag}>`. "
                f"Fix: Change the root tag to `<{error.expected_tag}>`."
            )
        else:
            return (
                f"Wrong tag for block at `{error.instead_tag}#{error.block[0]}`: "
                f'expected `<{error.expected_tag} id="{error.block[0]}">`, '
                f'but found `<{error.instead_tag} id="{error.block[0]}">`. '
                f"Fix: Change the tag to `<{error.expected_tag}>`."
            )
    elif isinstance(error, BlockExpectedIDsError):
        missing_elements = [f'<{elem.tag} id="{id}">' for id, elem in sorted(error.id2element.items())]
        elements_str = ", ".join(missing_elements)
        return f"Missing expected blocks: {elements_str}. Fix: Add these missing blocks with the correct IDs."

    elif isinstance(error, BlockUnexpectedIDError):
        selector = f"{error.element.tag}#{error.id}"
        return f"Unexpected block found at `{selector}`. Fix: Remove this unexpected block."

    elif isinstance(error, FoundInvalidIDError):
        if error.invalid_id is None:
            example = f"<{error.element.tag}>"
        else:
            example = f'<{error.element.tag} id="{error.invalid_id}">'
        return f"Invalid or missing ID attribute: {example}. Fix: Ensure all blocks have valid numeric IDs."
    else:
        return "Unknown block error. Fix: Review the block structure."


def _format_inline_error(error: InlineError | FoundInvalidIDError, block_id: int) -> str:
    if isinstance(error, InlineLostIDError):
        selector = _build_inline_selector(error.stack, block_id, element=error.element)
        return f"Element at `{selector}` is missing an ID attribute. Fix: Add the required ID attribute."

    elif isinstance(error, InlineExpectedIDsError):
        missing_elements = [f'<{elem.tag} id="{id}">' for id, elem in sorted(error.id2element.items())]
        elements_str = ", ".join(missing_elements)
        return f"Missing expected inline elements: {elements_str}. Fix: Add these missing inline elements."

    elif isinstance(error, InlineUnexpectedIDError):
        selector = f"{error.element.tag}#{error.id}"
        return f"Unexpected inline element at `{selector}`. Fix: Remove this unexpected element."

    elif isinstance(error, InlineWrongTagCountError):
        tag = error.found_elements[0].tag if error.found_elements else "unknown"
        selector = _build_inline_selector(error.stack, block_id, tag=tag)
        expected = error.expected_count
        found = len(error.found_elements)

        if expected == 0 and found > 0:
            # 情况1: 不应该有，但发现了
            return (
                f"Found unexpected `<{tag}>` elements at `{selector}`. "
                f"There should be none, but {found} were found. "
                f"Fix: Remove all `<{tag}>` elements from this location."
            )
        elif expected > 0 and found == 0:
            # 情况2: 应该有，但没找到
            return (
                f"Missing `<{tag}>` elements at `{selector}`. "
                f"Expected {expected}, but none were found. "
                f"Fix: Add {expected} `<{tag}>` element(s) to this location."
            )
        elif found > expected:
            # 情况3: 数量过多
            extra = found - expected
            return (
                f"Too many `<{tag}>` elements at `{selector}`. "
                f"Expected {expected}, but found {found} ({extra} extra). "
                f"Fix: Remove {extra} `<{tag}>` element(s)."
            )
        else:
            # 情况4: 数量过少
            missing = expected - found
            return (
                f"Too few `<{tag}>` elements at `{selector}`. "
                f"Expected {expected}, but only found {found} ({missing} missing). "
                f"Fix: Add {missing} more `<{tag}>` element(s)."
            )
    elif isinstance(error, FoundInvalidIDError):
        if error.invalid_id is None:
            example = f"<{error.element.tag}>"
        else:
            example = f'<{error.element.tag} id="{error.invalid_id}">'
        return f"Invalid inline ID: {example}. Fix: Ensure inline elements have valid numeric IDs."
    else:
        return "Unknown inline error. Fix: Review the inline structure."


def _build_inline_selector(
    stack: list[Element],
    block_id: int,
    element: Element | None = None,
    tag: str | None = None,
) -> str:
    if element is not None:
        element_id = element.get("id")
        if element_id is not None:
            # 能用 ID 直接定位，就不必用路径定位
            return f"{element.tag}#{element_id}"
        tag = element.tag

    # 路径：block#id > parent > ... > tag
    block_tag = stack[0].tag if stack else "unknown"
    path_parts = [f"{block_tag}#{block_id}"]

    for parent in stack[1:]:
        path_parts.append(parent.tag)

    if tag:
        path_parts.append(tag)

    return " > ".join(path_parts)
