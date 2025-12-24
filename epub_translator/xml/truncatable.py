import re
from collections.abc import Generator
from dataclasses import dataclass
from enum import Enum, auto
from typing import Self
from xml.etree.ElementTree import Element

from tiktoken import Encoding

from epub_translator.serial.segment import Segment
from epub_translator.xml.xml import clone_element


class _TextLocation(Enum):
    TEXT = auto()
    TAIL = auto()


@dataclass
class _CutPoint:
    element: Element  # 需要切割的节点
    location: _TextLocation  # text 或 tail
    remaining_tokens: int  # 这个节点还能保留多少 tokens


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

        new_payload = clone_element(self._payload)

        # 1. 找到切割点
        cut_point = self._find_cut_point(self._payload, remain_tokens, from_tail=False)

        # 2. 剪枝
        self._prune_tree(new_payload, self._payload, cut_point, from_tail=False)

        # 3. 文本切割
        self._apply_cut(new_payload, self._payload, cut_point, from_tail=False)

        return self.__class__(self._encoding, new_payload)

    def truncate_before_tail(self, remain_tokens: int) -> Self:
        """保留尾部 N 个 tokens，删除头部"""
        if remain_tokens >= self.tokens:
            return self

        new_payload = clone_element(self._payload)

        # 1. 找到切割点
        cut_point = self._find_cut_point(self._payload, remain_tokens, from_tail=True)

        # 2. 剪枝
        self._prune_tree(new_payload, self._payload, cut_point, from_tail=True)

        # 3. 文本切割
        self._apply_cut(new_payload, self._payload, cut_point, from_tail=True)

        return self.__class__(self._encoding, new_payload)

    def _find_cut_point(self, element: Element, remain_tokens: int, from_tail: bool) -> _CutPoint | None:
        """找到切割点"""
        current_tokens = 0

        def search(elem: Element) -> _CutPoint | None:
            nonlocal current_tokens

            if not from_tail:
                # 正向遍历：text -> children -> tail
                if elem.text:
                    cache_key = (id(elem), _TextLocation.TEXT)
                    tokens_list = self._token_cache.get(cache_key, [])
                    tokens_count = len(tokens_list)

                    if current_tokens + tokens_count > remain_tokens:
                        return _CutPoint(elem, _TextLocation.TEXT, remain_tokens - current_tokens)
                    current_tokens += tokens_count

                for child in elem:
                    result = search(child)
                    if result:
                        return result

                    if child.tail:
                        cache_key = (id(child), _TextLocation.TAIL)
                        tokens_list = self._token_cache.get(cache_key, [])
                        tokens_count = len(tokens_list)

                        if current_tokens + tokens_count > remain_tokens:
                            return _CutPoint(child, _TextLocation.TAIL, remain_tokens - current_tokens)
                        current_tokens += tokens_count

            else:
                # 反向遍历：tail (倒序) -> children (倒序) -> text
                for i in range(len(elem) - 1, -1, -1):
                    child = elem[i]

                    if child.tail:
                        cache_key = (id(child), _TextLocation.TAIL)
                        tokens_list = self._token_cache.get(cache_key, [])
                        tokens_count = len(tokens_list)

                        if current_tokens + tokens_count > remain_tokens:
                            return _CutPoint(child, _TextLocation.TAIL, remain_tokens - current_tokens)
                        current_tokens += tokens_count

                    result = search(child)
                    if result:
                        return result

                if elem.text:
                    cache_key = (id(elem), _TextLocation.TEXT)
                    tokens_list = self._token_cache.get(cache_key, [])
                    tokens_count = len(tokens_list)

                    if current_tokens + tokens_count > remain_tokens:
                        return _CutPoint(elem, _TextLocation.TEXT, remain_tokens - current_tokens)
                    current_tokens += tokens_count

            return None

        return search(element)

    def _prune_tree(
        self,
        new_element: Element,
        original_element: Element,
        cut_point: _CutPoint | None,
        from_tail: bool,
    ) -> None:
        """根据切割点剪枝"""
        if not cut_point:
            return

        def prune(new_elem: Element, orig_elem: Element) -> bool:
            """返回 True 表示找到了切割点"""
            if orig_elem is cut_point.element:
                # 找到切割点
                if cut_point.location == _TextLocation.TEXT:
                    # 切割在 text 上，删除所有子节点
                    new_elem[:] = []
                return True

            if not from_tail:
                # 正向剪枝
                children_to_remove = []
                found_cut_point = False
                for i, (new_child, orig_child) in enumerate(zip(new_elem, orig_elem)):
                    if orig_child is cut_point.element and cut_point.location == _TextLocation.TAIL:
                        # 找到切割点在 tail 上，删除后续兄弟节点
                        children_to_remove = list(range(i + 1, len(new_elem)))
                        found_cut_point = True
                        break

                    if prune(new_child, orig_child):
                        # 切割点在子节点内部，删除后续兄弟节点
                        children_to_remove = list(range(i + 1, len(new_elem)))
                        found_cut_point = True
                        break

                for idx in reversed(children_to_remove):
                    del new_elem[idx]

                return found_cut_point

            else:
                # 反向剪枝
                children_to_remove = []
                found_cut_point = False
                for i in range(len(new_elem) - 1, -1, -1):
                    new_child = new_elem[i]
                    orig_child = orig_elem[i]

                    if orig_child is cut_point.element and cut_point.location == _TextLocation.TAIL:
                        # 找到切割点在 tail 上，删除前面的兄弟节点和 parent.text
                        children_to_remove = list(range(0, i))
                        new_elem.text = None
                        found_cut_point = True
                        break

                    if prune(new_child, orig_child):
                        # 切割点在子节点内部，删除前面的兄弟节点和 parent.text
                        children_to_remove = list(range(0, i))
                        new_elem.text = None
                        found_cut_point = True
                        break

                for idx in reversed(children_to_remove):
                    del new_elem[idx]

                return found_cut_point

        prune(new_element, original_element)

    def _apply_cut(
        self,
        new_element: Element,
        original_element: Element,
        cut_point: _CutPoint | None,
        from_tail: bool,
    ) -> None:
        """对切割点进行文本截断"""
        if not cut_point:
            return

        def apply(new_elem: Element, orig_elem: Element) -> bool:
            """返回 True 表示找到并处理了切割点"""
            if orig_elem is cut_point.element:
                # 找到切割点，进行文本截断
                cache_key = (id(orig_elem), cut_point.location)
                tokens_list = self._token_cache.get(cache_key, [])

                if from_tail:
                    # 从尾部保留
                    truncated = self._decode_tokens(tokens_list[-cut_point.remaining_tokens :]).lstrip()
                else:
                    # 从头部保留
                    truncated = self._decode_tokens(tokens_list[: cut_point.remaining_tokens]).strip()

                text_attr = "text" if cut_point.location == _TextLocation.TEXT else "tail"
                setattr(new_elem, text_attr, truncated)
                return True

            # 递归查找
            for new_child, orig_child in zip(new_elem, orig_elem):
                if apply(new_child, orig_child):
                    return True

            return False

        apply(new_element, original_element)

    def _iter_text_fragments(self, element: Element) -> Generator[str, None, None]:
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
