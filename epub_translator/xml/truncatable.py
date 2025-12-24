import copy
import re
from enum import Enum
from typing import Self
from xml.etree.ElementTree import Element

from tiktoken import Encoding

from epub_translator.serial.segment import Segment


class _TextLocation(Enum):
    """文本位置：节点的 text 或 tail"""

    TEXT = "text"
    TAIL = "tail"


class TruncatableXML(Segment[Element]):
    _payload: Element

    def __init__(self, encoding: Encoding, payload: Element) -> None:
        self._encoding: Encoding = encoding
        self._payload = payload
        self._token_cache: dict[tuple[int, _TextLocation], list[int]] = {}
        self._build_cache(self._payload)

    @property
    def text(self) -> str:
        """返回 XML 树中所有文本内容的拼接结果"""
        fragments = list(self._iter_text_fragments(self._payload))
        if not fragments:
            return ""

        # 前面的片段 lstrip()，最后一个 strip()
        result_fragments = []
        for i, frag in enumerate(fragments):
            if i == len(fragments) - 1:
                processed = frag.strip()
            else:
                processed = frag.lstrip()
            if processed:
                result_fragments.append(processed)

        return "".join(result_fragments)

    @property
    def tokens(self) -> int:
        """返回所有文本片段的 token 总数"""
        return sum(len(tokens) for tokens in self._token_cache.values())

    @property
    def payload(self) -> Element:
        return self._payload

    def truncate_after_head(self, remain_tokens: int) -> Self:
        """保留头部 N 个 tokens，删除尾部"""
        if remain_tokens >= self.tokens:
            return self

        new_payload = copy.deepcopy(self._payload)
        current_tokens = 0

        def truncate_forward(element: Element, original: Element) -> bool:
            """返回 True 表示已完成截断，应停止遍历"""
            nonlocal current_tokens

            # 处理 element.text
            if element.text:
                text = self._normalize_whitespace(element.text).lstrip()
                if text:
                    # 从缓存中获取 tokens
                    cache_key = (id(original), _TextLocation.TEXT)
                    text_tokens_list = self._token_cache.get(cache_key, [])
                    text_tokens = len(text_tokens_list)

                    if current_tokens + text_tokens <= remain_tokens:
                        current_tokens += text_tokens
                    else:
                        # 需要截断这个 text
                        remaining = remain_tokens - current_tokens
                        element.text = self._decode_tokens(text_tokens_list[:remaining]).strip()
                        # 删除所有子节点
                        element[:] = []
                        return True

            # 递归处理子节点
            children_to_remove = []
            for i, (child, original_child) in enumerate(zip(element, original)):
                if truncate_forward(child, original_child):
                    # 截断发生在这个子节点中，删除后续所有兄弟节点
                    children_to_remove = list(range(i + 1, len(element)))
                    break

                # 处理 child.tail
                if child.tail:
                    tail = self._normalize_whitespace(child.tail).lstrip()
                    if tail:
                        # 从缓存中获取 tokens
                        cache_key = (id(original_child), _TextLocation.TAIL)
                        tail_tokens_list = self._token_cache.get(cache_key, [])
                        tail_tokens = len(tail_tokens_list)

                        if current_tokens + tail_tokens <= remain_tokens:
                            current_tokens += tail_tokens
                        else:
                            # 需要截断这个 tail
                            remaining = remain_tokens - current_tokens
                            child.tail = self._decode_tokens(tail_tokens_list[:remaining]).strip()
                            # 删除后续所有兄弟节点
                            children_to_remove = list(range(i + 1, len(element)))
                            return True

            # 删除标记的子节点
            for idx in reversed(children_to_remove):
                del element[idx]

            return len(children_to_remove) > 0

        truncate_forward(new_payload, self._payload)
        return self.__class__(self._encoding, new_payload)

    def truncate_before_tail(self, remain_tokens: int) -> Self:
        """保留尾部 N 个 tokens，删除头部"""
        if remain_tokens >= self.tokens:
            return self

        new_payload = copy.deepcopy(self._payload)
        current_tokens = 0

        def truncate_backward(element: Element, original: Element) -> bool:
            """返回 True 表示已完成截断，应停止遍历"""
            nonlocal current_tokens

            # 从后往前处理子节点
            children_to_remove = []
            for i in range(len(element) - 1, -1, -1):
                child = element[i]
                original_child = original[i]

                # 先处理 child.tail
                if child.tail:
                    tail = self._normalize_whitespace(child.tail).lstrip()
                    if tail:
                        # 从缓存中获取 tokens
                        cache_key = (id(original_child), _TextLocation.TAIL)
                        tail_tokens_list = self._token_cache.get(cache_key, [])
                        tail_tokens = len(tail_tokens_list)

                        if current_tokens + tail_tokens <= remain_tokens:
                            current_tokens += tail_tokens
                        else:
                            # 需要截断这个 tail（从尾部保留）
                            remaining = remain_tokens - current_tokens
                            truncated = self._decode_tokens(tail_tokens_list[-remaining:])
                            child.tail = truncated.lstrip()
                            # 删除前面所有兄弟节点和 parent.text
                            children_to_remove = list(range(0, i))
                            element.text = None
                            return True

                # 递归处理子节点
                if truncate_backward(child, original_child):
                    # 截断发生在这个子节点中，删除前面所有兄弟节点
                    children_to_remove = list(range(0, i))
                    element.text = None
                    break

            # 删除标记的子节点
            for idx in reversed(children_to_remove):
                del element[idx]

            if len(children_to_remove) > 0:
                return True

            # 最后处理 element.text（如果还有剩余 tokens）
            if element.text:
                text = self._normalize_whitespace(element.text).lstrip()
                if text:
                    # 从缓存中获取 tokens
                    cache_key = (id(original), _TextLocation.TEXT)
                    text_tokens_list = self._token_cache.get(cache_key, [])
                    text_tokens = len(text_tokens_list)

                    if current_tokens + text_tokens <= remain_tokens:
                        current_tokens += text_tokens
                    else:
                        # 需要截断这个 text（从尾部保留）
                        remaining = remain_tokens - current_tokens
                        truncated = self._decode_tokens(text_tokens_list[-remaining:])
                        element.text = truncated.lstrip()
                        return True

            return False

        truncate_backward(new_payload, self._payload)
        return self.__class__(self._encoding, new_payload)

    def _iter_text_fragments(self, element: Element):
        """按照先序遍历收集所有文本片段（text 和 tail）"""
        if element.text:
            yield self._normalize_whitespace(element.text)
        for child in element:
            yield from self._iter_text_fragments(child)
            if child.tail:
                yield self._normalize_whitespace(child.tail)

    def _build_cache(self, element: Element) -> None:
        """递归构建 token 缓存"""
        # 处理 element.text
        if element.text:
            text = self._normalize_whitespace(element.text).lstrip()
            if text:
                tokens = self._encoding.encode(text)
                self._token_cache[(id(element), _TextLocation.TEXT)] = tokens

        # 递归处理子节点
        for child in element:
            self._build_cache(child)
            # 处理 child.tail
            if child.tail:
                tail = self._normalize_whitespace(child.tail).lstrip()
                if tail:
                    tokens = self._encoding.encode(tail)
                    self._token_cache[(id(child), _TextLocation.TAIL)] = tokens

    def _normalize_whitespace(self, text: str) -> str:
        r"""将 \s+ 替换成单个空格"""
        return re.sub(r"\s+", " ", text)

    def _decode_tokens(self, tokens: list[int]) -> str:
        """将 token 列表解码为文本"""
        if not tokens:
            return ""
        return self._encoding.decode(tokens)
