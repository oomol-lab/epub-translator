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
    block_errors: list[tuple[BlockError | FoundInvalidIDError, int]] = []
    inline_errors_by_block: dict[int, list[tuple[InlineError | FoundInvalidIDError, int]]] = {}

    for error in errors:
        if isinstance(error, BlockContentError):
            # 收集 inline 错误
            block_id = error.id
            inline_error_list = []
            for inline_error in error.errors:
                level = _get_inline_error_level(inline_error)
                inline_error_list.append((inline_error, level))
            if inline_error_list:
                inline_errors_by_block[block_id] = inline_error_list
        else:
            # 收集 block 错误
            level = _get_block_error_level(error)
            block_errors.append((error, level))

    # 计算 block 分数（忽略 BlockContentError）
    block_score = sum(_LEVEL_WEIGHT**level for _, level in block_errors)

    # 计算每个 block ID 的 inline 分数
    inline_scores: dict[int, int] = {}
    for block_id, inline_error_list in inline_errors_by_block.items():
        inline_scores[block_id] = sum(_LEVEL_WEIGHT**level for _, level in inline_error_list)

    # 生成错误消息：展开所有错误，按等级排序，截取前 max_errors 个
    # 使用两个列表分别存储 block 和 inline 错误信息
    all_sorted_errors: list[tuple[int, int, bool, int, int | None]] = []
    # (level, original_idx, is_block, error_idx_in_list, block_id_or_none)

    # 添加 block 错误（is_block=True, block_id=None）
    for idx, (_, level) in enumerate(block_errors):
        all_sorted_errors.append((level, idx, True, idx, None))

    # 展开并添加 inline 错误（is_block=False, block_id=实际ID）
    inline_idx = 0
    inline_flat_list: list[tuple[InlineError | FoundInvalidIDError, int]] = []
    for block_id, inline_error_list in inline_errors_by_block.items():
        for error, level in inline_error_list:
            all_sorted_errors.append((level, len(block_errors) + inline_idx, False, inline_idx, block_id))
            inline_flat_list.append((error, block_id))
            inline_idx += 1

    # 按等级降序排序（高等级在前），相同等级保留自然顺序
    all_sorted_errors.sort(key=lambda x: (-x[0], x[1]))

    # 截取前 max_errors 个
    selected_errors = all_sorted_errors[:max_errors]

    # 生成错误消息
    if not selected_errors:
        error_message = None
    else:
        # 重新组织为按 block 分组
        block_error_messages: list[str] = []
        inline_errors_grouped: dict[int, list[InlineError | FoundInvalidIDError]] = {}

        for _, _, is_block, error_idx, block_id in selected_errors:
            if is_block:
                # Block 级别错误
                error, _ = block_errors[error_idx]
                block_error_messages.append(_format_block_error(root_tag, error))
            else:
                # Inline 级别错误，按 block_id 分组
                error, actual_block_id = inline_flat_list[error_idx]
                if actual_block_id not in inline_errors_grouped:
                    inline_errors_grouped[actual_block_id] = []
                inline_errors_grouped[actual_block_id].append(error)

        # 生成 inline 错误的消息段落
        inline_block_messages: list[str] = []
        for block_id, inline_error_list in inline_errors_grouped.items():
            inline_messages = [_format_inline_error(err, block_id, root_tag) for err in inline_error_list]
            block_message = f"In {root_tag}#{block_id}:\n" + "\n".join(f"  - {msg}" for msg in inline_messages)
            inline_block_messages.append(block_message)

        # 组合所有错误消息
        all_messages = block_error_messages + inline_block_messages
        error_message = "\n\n".join(all_messages) if all_messages else None

    return ValidationReporting(
        error_message=error_message,
        block_score=block_score,
        inline_scores=inline_scores,
    )


def _get_block_error_level(error: BlockError | FoundInvalidIDError) -> int:
    """获取 block 级别错误的等级"""
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
    """获取 inline 级别错误的等级"""
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


def _format_block_error(root_tag: str, error: BlockError | FoundInvalidIDError) -> str:
    """格式化 block 级别错误消息"""
    if isinstance(error, BlockWrongRootTagError):
        return (
            f"Root tag mismatch: expected `{error.expected_tag}`, but found `{error.instead_tag}`. "
            f"Fix: Change the root tag to `{error.expected_tag}`."
        )
    elif isinstance(error, BlockExpectedIDsError):
        ids_str = ", ".join(f"{root_tag}#{id}" for id in error.ids)
        return f"Missing expected blocks: {ids_str}. Fix: Add these missing blocks with the correct IDs."
    elif isinstance(error, BlockUnexpectedIDError):
        selector = f"{error.element.tag}#{error.id}"
        return f"Unexpected block found at `{selector}`. Fix: Remove this unexpected block."
    elif isinstance(error, FoundInvalidIDError):
        invalid_id = error.invalid_id if error.invalid_id else "missing"
        return f"Invalid or missing ID attribute (found: {invalid_id}). Fix: Ensure all blocks have valid numeric IDs."
    else:
        return "Unknown block error. Fix: Review the block structure."


def _format_inline_error(error: InlineError | FoundInvalidIDError, block_id: int, root_tag: str) -> str:
    """格式化 inline 级别错误消息"""
    if isinstance(error, InlineLostIDError):
        selector = _build_inline_selector(error.element, error.stack, block_id, root_tag)
        return f"Element at `{selector}` is missing an ID attribute. Fix: Add the required ID attribute."
    elif isinstance(error, InlineExpectedIDsError):
        ids_str = ", ".join(f"#{id}" for id in error.ids)
        return f"Missing expected inline elements with IDs: {ids_str}. Fix: Add these missing inline elements."
    elif isinstance(error, InlineUnexpectedIDError):
        selector = f"{error.element.tag}#{error.id}"
        return f"Unexpected inline element at `{selector}`. Fix: Remove this unexpected element."
    elif isinstance(error, InlineWrongTagCountError):
        tag = error.found_elements[0].tag if error.found_elements else "unknown"
        selector = _build_inline_selector_from_stack(tag, error.stack, block_id, root_tag)
        return (
            f"Wrong count of `{tag}` elements at `{selector}`: "
            f"expected {error.expected_count}, found {len(error.found_elements)}. "
            f"Fix: Adjust the number of `{tag}` elements to match the expected count."
        )
    elif isinstance(error, FoundInvalidIDError):
        invalid_id = error.invalid_id if error.invalid_id else "missing"
        return f"Invalid inline ID (found: {invalid_id}). Fix: Ensure inline elements have valid numeric IDs."
    else:
        return "Unknown inline error. Fix: Review the inline structure."


def _build_inline_selector(element: Element, stack: list[Element], block_id: int, root_tag: str) -> str:
    """构建 inline 元素的 selector（有 ID 时用 span#42，无 ID 时用栈路径）"""
    element_id = element.get("id")
    if element_id is not None:
        return f"{element.tag}#{element_id}"
    else:
        # 从 block 开始，用 > 符号构建路径
        path_parts = [f"{root_tag}#{block_id}"]
        for parent in stack:
            path_parts.append(parent.tag)
        path_parts.append(element.tag)
        return " > ".join(path_parts)


def _build_inline_selector_from_stack(tag: str, stack: list[Element], block_id: int, root_tag: str) -> str:
    """从栈构建 inline selector"""
    path_parts = [f"{root_tag}#{block_id}"]
    for parent in stack:
        path_parts.append(parent.tag)
    path_parts.append(tag)
    return " > ".join(path_parts)
