from collections.abc import Generator
from dataclasses import dataclass
from xml.etree.ElementTree import Element

from tiktoken import Encoding

from ..segment import BlockSegment, BlockSubmitter, TextSegment, search_text_segments
from ..xml import plain_text
from .common import DATA_ORIGIN_LEN_KEY
from .validation import LEVEL_DEPTH, generate_error_message, nest_as_errors_group, truncate_errors_group


@dataclass
class _BlockStatus:
    weight: int
    submitter: BlockSubmitter


# 以爬山算法，将 LLM 中提交的内容中挑选出完成度更高的部分。
# 它通过拒绝每个子部分的相对低完成度提交，锁定每个子部分只能往更高完成度的方向移动
class HillClimbing:
    def __init__(
        self,
        encoding: Encoding,
        max_fill_displaying_errors: int,
        block_segment: BlockSegment,
    ) -> None:
        self._encoding: Encoding = encoding
        self._max_fill_displaying_errors: int = max_fill_displaying_errors
        self._block_statuses: dict[int, _BlockStatus] = {}
        self._block_segment: BlockSegment = block_segment

    def request_element(self) -> Element:
        element = self._block_segment.create_element()
        for child_element in element:
            text = plain_text(child_element)
            tokens = self._encoding.encode(text)
            child_element.set(DATA_ORIGIN_LEN_KEY, str(len(tokens)))
        return element

    def gen_text_segments(self) -> Generator[list[TextSegment] | None, None, None]:
        for inline_segment in self._block_segment:
            id = inline_segment.id
            assert id is not None
            status = self._block_statuses.get(id, None)
            if status is None:
                yield None
            else:
                yield list(
                    search_text_segments(root=status.submitter.submitted_element),
                )

    def submit(self, element: Element) -> str | None:
        error_message, elevatory_block_weights = self._validate_block_weights_and_error_message(element)
        if elevatory_block_weights:
            for submitter in self._block_segment.submit(element):
                weight = elevatory_block_weights.get(submitter.id, None)
                if weight is None:
                    pass
                elif submitter.id not in self._block_statuses:
                    self._block_statuses[submitter.id] = _BlockStatus(
                        weight=weight,
                        submitter=submitter,
                    )
                else:
                    status = self._block_statuses[submitter.id]
                    status.weight = weight
                    status.submitter = submitter
        return error_message

    def _validate_block_weights_and_error_message(self, element: Element) -> tuple[str | None, dict[int, int] | None]:
        errors_group = nest_as_errors_group(
            errors=self._block_segment.validate(element),
        )
        if errors_group is None:
            return None, None

        elevatory_block_weights: dict[int, int] = {}
        for block_group in errors_group.block_groups:
            block_id = block_group.block_id
            status = self._block_statuses.get(block_id, None)
            if status is None or status.weight >= block_group.weight:
                elevatory_block_weights[block_id] = block_group.weight
            else:
                # 对于 AI 显著提升的块，下次应该让出注意力，让 AI 提升那些没有被提升的块
                for child_error in block_group.errors:
                    child_error.level -= LEVEL_DEPTH

        origin_errors_count = errors_group.errors_count
        errors_group = truncate_errors_group(
            errors_group=errors_group,
            max_errors=self._max_fill_displaying_errors,
        )
        if errors_group is None:
            return None, elevatory_block_weights

        message = generate_error_message(
            encoding=self._encoding,
            errors_group=errors_group,
            omitted_count=origin_errors_count - errors_group.errors_count,
        )
        return message, elevatory_block_weights
