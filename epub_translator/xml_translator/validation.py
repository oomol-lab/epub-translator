from collections.abc import Iterable
from dataclasses import dataclass
from xml.etree.ElementTree import Element

from ..segment import (
    BlockContentError,
    BlockError,
    BlockExpectedIDsError,
    BlockUnexpectedIDError,
    BlockWrongRootTagError,
    FoundInvalidIDError,
    InlineError,
    InlineExpectedIDsError,
    InlineLostIDError,
    InlineUnexpectedIDError,
    InlineWrongTagCountError,
)


@dataclass
class _BlockErrorInfo:
    """Block 错误信息"""

    error: BlockError | FoundInvalidIDError
    level: int
    weight: int  # 用于排序和计分的权重


@dataclass
class _InlineErrorInfo:
    """Inline 错误信息"""

    error: InlineError | FoundInvalidIDError
    level: int
    weight: int  # 用于排序和计分的权重


@dataclass
class _ErrorGroup:
    """按 block 分组的错误"""

    block_id: int | None  # None 表示没有特定 block_id 的错误
    block_errors: list[_BlockErrorInfo]
    inline_errors: list[_InlineErrorInfo]
    total_score: int


_LEVEL_WEIGHT = 3

_BLOCK_WRONG_ROOT_TAG_LEVEL = 5
_BLOCK_EXPECTED_IDS_LEVEL = 5
_BLOCK_FOUND_INVALID_ID_LEVEL = 4
_BLOCK_UNEXPECTED_ID_LEVEL = 3

_INLINE_LOST_ID_LEVEL = 2
_INLINE_EXPECTED_IDS_LEVEL = 2
_INLINE_FOUND_INVALID_ID_LEVEL = 1
_INLINE_WRONG_TAG_COUNT_LEVEL = 0
_INLINE_UNEXPECTED_ID_LEVEL = 0


@dataclass
class ValidationReporting:
    error_message: str | None
    block_score: int
    inline_scores: dict[int, int]


def validate(
    root_tag: str,
    errors: Iterable[BlockError | FoundInvalidIDError],
    max_errors: int,
) -> ValidationReporting:
    # 收集并分类所有错误
    error_groups = _collect_and_group_errors(errors)

    # 计算 block 分数和 inline 分数
    block_score = _calculate_block_score(error_groups)
    inline_scores = _calculate_inline_scores(error_groups)

    # 生成错误消息
    error_message = _build_error_message(root_tag, error_groups, max_errors)

    return ValidationReporting(
        error_message=error_message,
        block_score=block_score,
        inline_scores=inline_scores,
    )


def _collect_and_group_errors(
    errors: Iterable[BlockError | FoundInvalidIDError],
) -> dict[int | None, _ErrorGroup]:
    """收集并按 block_id 分组错误"""
    error_groups: dict[int | None, _ErrorGroup] = {}

    for error in errors:
        if isinstance(error, BlockContentError):
            # Inline 错误，按 block_id 分组
            block_id = error.id
            if block_id not in error_groups:
                error_groups[block_id] = _ErrorGroup(
                    block_id=block_id,
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
            # Block 错误，统一归到 None 组（表示全局错误）
            if None not in error_groups:
                error_groups[None] = _ErrorGroup(
                    block_id=None,
                    block_errors=[],
                    inline_errors=[],
                    total_score=0,
                )

            level = _get_block_error_level(error)
            weight = _calculate_error_weight(error, level)
            error_groups[None].block_errors.append(_BlockErrorInfo(error=error, level=level, weight=weight))

    # 计算每组的总分并排序内部错误
    for group in error_groups.values():
        # 按 level 降序排序（高等级在前）
        group.block_errors.sort(key=lambda e: -e.level)
        group.inline_errors.sort(key=lambda e: -e.level)
        # 计算总分
        group.total_score = sum(e.weight for e in group.block_errors) + sum(e.weight for e in group.inline_errors)

    return error_groups


def _calculate_block_score(error_groups: dict[int | None, _ErrorGroup]) -> int:
    """计算 block 分数（仅包括 block 级别错误）"""
    if None not in error_groups:
        return 0
    return sum(e.weight for e in error_groups[None].block_errors)


def _calculate_inline_scores(error_groups: dict[int | None, _ErrorGroup]) -> dict[int, int]:
    """计算每个 block ID 的 inline 分数"""
    inline_scores: dict[int, int] = {}
    for block_id, group in error_groups.items():
        if block_id is not None and group.inline_errors:
            inline_scores[block_id] = sum(e.weight for e in group.inline_errors)
    return inline_scores


def _build_error_message(
    root_tag: str,
    error_groups: dict[int | None, _ErrorGroup],
    max_errors: int,
) -> str | None:
    """构建错误消息"""
    if not error_groups:
        return None

    # 统计总错误数
    total_error_count = sum(len(g.block_errors) + len(g.inline_errors) for g in error_groups.values())
    if total_error_count == 0:
        return None

    # 按总分降序排序错误组
    sorted_groups = sorted(error_groups.values(), key=lambda g: -g.total_score)

    # 构建消息段落
    messages: list[str] = []
    shown_error_count = 0

    for group in sorted_groups:
        if shown_error_count >= max_errors:
            break

        group_messages: list[str] = []

        # 添加 block 错误（如果有）
        for error_info in group.block_errors:
            if shown_error_count >= max_errors:
                break
            group_messages.append(_format_block_error(error_info.error))
            shown_error_count += 1

        # 添加 inline 错误（如果有）
        inline_messages: list[str] = []
        if group.block_id is not None:  # inline 错误必须有 block_id
            for error_info in group.inline_errors:
                if shown_error_count >= max_errors:
                    break
                inline_messages.append(_format_inline_error(error_info.error, group.block_id))
                shown_error_count += 1

        if inline_messages:
            group_messages.extend(f"  - {msg}" for msg in inline_messages)

        # 如果这个组有消息，组合成一个段落
        if group_messages:
            if group.block_id is not None:
                # 有 block_id 的组，添加标题
                # 尝试从 inline errors 中获取实际的 block tag
                block_tag = root_tag
                if group.inline_errors:
                    first_error = group.inline_errors[0].error
                    if isinstance(first_error, (InlineLostIDError, InlineWrongTagCountError)) and first_error.stack:
                        block_tag = first_error.stack[0].tag
                messages.append(f"In {block_tag}#{group.block_id}:\n" + "\n".join(group_messages))
            else:
                # 全局错误，直接添加
                messages.extend(group_messages)

    # 组合所有消息
    if not messages:
        return None

    # 添加头部说明
    header = f"Found {total_error_count} error(s) in total:"
    result = header + "\n\n" + "\n\n".join(messages)

    # 如果有省略的错误，添加尾部说明
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
    if isinstance(error, BlockWrongRootTagError):
        return _BLOCK_WRONG_ROOT_TAG_LEVEL
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
    """格式化 block 级别错误消息"""
    if isinstance(error, BlockWrongRootTagError):
        return (
            f"Root tag mismatch: expected `{error.expected_tag}`, but found `{error.instead_tag}`. "
            f"Fix: Change the root tag to `{error.expected_tag}`."
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
    """格式化 inline 级别错误消息"""
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
    # 如果 element 有 id，直接返回 tag#id
    if element is not None:
        element_id = element.get("id")
        if element_id is not None:
            return f"{element.tag}#{element_id}"
        tag = element.tag

    # 构建路径：block#id > parent > ... > tag
    # stack[0] 是 block 元素本身，从它获取 block_tag
    block_tag = stack[0].tag if stack else "unknown"
    path_parts = [f"{block_tag}#{block_id}"]

    # stack[0] 已经作为 block，从 stack[1:] 开始添加中间父元素
    for parent in stack[1:]:
        path_parts.append(parent.tag)

    # 最后添加目标元素的 tag
    if tag:
        path_parts.append(tag)

    return " > ".join(path_parts)
