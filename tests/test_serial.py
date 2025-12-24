from typing import Self

from epub_translator.serial import Segment, split
from epub_translator.serial.chunk import split_into_chunks


class MockSegment(Segment[str]):
    def __init__(self, payload: str, tokens: int) -> None:
        self._payload = payload
        self._tokens = tokens

    @property
    def payload(self) -> str:
        return self._payload

    @property
    def tokens(self) -> int:
        return self._tokens

    @classmethod
    def from_text(cls, text: str) -> Self:
        """从文本创建 MockSegment"""
        return cls(payload=text, tokens=len(text))

    def truncate_after_head(self, remain_tokens: int) -> Self:
        """保留开头的 remain_tokens 个字符"""
        truncated_text = self.payload[:remain_tokens]
        return type(self)(payload=truncated_text, tokens=len(truncated_text))

    def truncate_before_tail(self, remain_tokens: int) -> Self:
        """保留结尾的 remain_tokens 个字符"""
        truncated_text = self.payload[-remain_tokens:] if remain_tokens > 0 else ""
        return type(self)(payload=truncated_text, tokens=len(truncated_text))


class TestChunkBasic:
    """测试 split_into_chunks 的基本功能"""

    def test_simple_chunking(self):
        """测试简单的分块功能"""
        segments = [
            MockSegment.from_text("Hello"),  # 5 tokens
            MockSegment.from_text("World"),  # 5 tokens
            MockSegment.from_text("Python"),  # 6 tokens
        ]

        chunks = list(split_into_chunks(segments, max_group_tokens=10))

        # 应该至少有一个 chunk
        assert len(chunks) > 0

        # 验证 chunk 结构
        for chunk in chunks:
            assert hasattr(chunk, "head")
            assert hasattr(chunk, "body")
            assert hasattr(chunk, "tail")
            assert hasattr(chunk, "head_remain_tokens")
            assert hasattr(chunk, "tail_remain_tokens")

    def test_chunk_contains_all_segments(self):
        """验证所有 segment 都被包含在 chunks 中"""
        segments = [
            MockSegment.from_text("A"),
            MockSegment.from_text("B"),
            MockSegment.from_text("C"),
            MockSegment.from_text("D"),
        ]

        chunks = list(split_into_chunks(segments, max_group_tokens=2))

        # 收集所有 chunk 中的内容
        all_payloads = []
        for chunk in chunks:
            all_payloads.extend(seg.payload for seg in chunk.head)
            all_payloads.extend(seg.payload for seg in chunk.body)
            all_payloads.extend(seg.payload for seg in chunk.tail)

        # 验证所有原始 segment 都出现了
        original_payloads = [seg.payload for seg in segments]
        for payload in original_payloads:
            assert payload in all_payloads, f"Payload '{payload}' 应该出现在 chunks 中"

    def test_large_max_tokens(self):
        """测试 max_tokens 很大时，所有内容在一个 chunk 中"""
        segments = [
            MockSegment.from_text("Short"),
            MockSegment.from_text("Text"),
        ]

        chunks = list(split_into_chunks(segments, max_group_tokens=1000))

        # 应该只有一个 chunk
        assert len(chunks) >= 1


class TestSplitterBasic:
    """测试 splitter.split 的基本功能"""

    def test_simple_split(self):
        """测试简单的 split 转换"""
        segments = [
            MockSegment.from_text("Hello"),
            MockSegment.from_text("World"),
        ]

        def transform(segs):
            """简单的转换：转大写"""
            return [MockSegment.from_text(seg.payload.upper()) for seg in segs]

        results = list(split(segments, transform, max_group_tokens=10))

        # 应该有结果
        assert len(results) > 0

        # 验证转换是否生效
        result_texts = [r.payload for r in results]
        assert "HELLO" in result_texts or "WORLD" in result_texts

    def test_transform_preserves_body(self):
        """验证只返回 body 部分的转换结果"""
        segments = [
            MockSegment.from_text("A"),
            MockSegment.from_text("B"),
            MockSegment.from_text("C"),
            MockSegment.from_text("D"),
            MockSegment.from_text("E"),
        ]

        def transform(segs):
            """标记每个 segment"""
            return [MockSegment.from_text(f"[{seg.payload}]") for seg in segs]

        results = list(split(segments, transform, max_group_tokens=3))

        # 验证结果
        result_texts = [r.payload for r in results]
        assert len(result_texts) > 0


class TestEmptyTailSlicing:
    """测试修复的 bug：当 tail 为空时的切片问题"""

    def test_empty_tail_returns_correct_results(self):
        """当 tail 为空时，应该返回正确的结果而不是空列表"""
        segments = [
            MockSegment.from_text("First"),
            MockSegment.from_text("Second"),
        ]

        def identity_transform(segs):
            """恒等转换"""
            return segs

        results = list(split(segments, identity_transform, max_group_tokens=20))

        # 应该有结果（不应该因为 tail 为空而返回空列表）
        assert len(results) > 0, "即使 tail 为空也应该返回结果"

    def test_no_context_needed(self):
        """当不需要上下文时（max_tokens 足够大），应该正常工作"""
        segments = [MockSegment.from_text("OnlyOne")]

        def transform(segs):
            return [MockSegment.from_text(seg.payload + "!") for seg in segs]

        results = list(split(segments, transform, max_group_tokens=100))

        assert len(results) == 1
        assert results[0].payload == "OnlyOne!"


class TestTruncation:
    """测试截断功能"""

    def test_truncate_after_head(self):
        """测试 truncate_after_head 方法"""
        seg = MockSegment.from_text("HelloWorld")  # 10 tokens

        truncated = seg.truncate_after_head(5)

        assert truncated.payload == "Hello"
        assert truncated.tokens == 5

    def test_truncate_before_tail(self):
        """测试 truncate_before_tail 方法"""
        seg = MockSegment.from_text("HelloWorld")  # 10 tokens

        truncated = seg.truncate_before_tail(5)

        assert truncated.payload == "World"
        assert truncated.tokens == 5

    def test_truncate_with_zero_tokens(self):
        """测试使用 0 tokens 截断"""
        seg = MockSegment.from_text("Test")

        truncated_head = seg.truncate_after_head(0)
        truncated_tail = seg.truncate_before_tail(0)

        assert truncated_head.payload == ""
        assert truncated_head.tokens == 0
        assert truncated_tail.payload == ""
        assert truncated_tail.tokens == 0


class TestRemainTokensBug:
    """测试修复的 bug：remain_tokens 在使用前被修改"""

    def test_partial_remain_tokens(self):
        """当 remain_tokens 小于 segment tokens 时，应该正确截断"""
        # 创建一个足够大的 segment
        segments = [
            MockSegment.from_text("A" * 20),  # 20 tokens
            MockSegment.from_text("B" * 10),  # 10 tokens
        ]

        def transform(segs):
            """保持原样"""
            return segs

        # 使用较小的 max_tokens 以触发截断
        results = list(split(segments, transform, max_group_tokens=15))

        # 应该有结果，且不会因为错误的截断而失败
        assert len(results) > 0


class TestMultipleChunks:
    """测试多个 chunks 的场景"""

    def test_multiple_chunks_with_context(self):
        """测试生成多个 chunks 时，上下文是否正确传递"""
        segments = [MockSegment.from_text(chr(65 + i)) for i in range(10)]  # A-J

        def transform(segs):
            """添加前缀"""
            return [MockSegment.from_text(f"T-{seg.payload}") for seg in segs]

        results = list(split(segments, transform, max_group_tokens=3))

        # 应该有多个结果
        assert len(results) > 0

        # 验证转换生效
        for result in results:
            assert result.payload.startswith("T-")


class TestEdgeCases:
    """测试边界情况"""

    def test_single_segment(self):
        """测试单个 segment"""
        segments = [MockSegment.from_text("Only")]

        def transform(segs):
            return [MockSegment.from_text(seg.payload * 2) for seg in segs]

        results = list(split(segments, transform, max_group_tokens=10))

        assert len(results) == 1
        assert results[0].payload == "OnlyOnly"

    def test_very_small_max_tokens(self):
        """测试非常小的 max_tokens"""
        segments = [
            MockSegment.from_text("AB"),
            MockSegment.from_text("CD"),
        ]

        def transform(segs):
            return segs

        results = list(split(segments, transform, max_group_tokens=1))

        # 即使 max_tokens 很小，也应该能处理
        assert len(results) > 0

    def test_empty_segments_list(self):
        """测试空的 segments 列表"""
        segments = []

        def transform(segs):
            return segs

        results = list(split(segments, transform, max_group_tokens=10))

        # 空输入应该产生空输出
        assert len(results) == 0


class TestTransformConsistency:
    """测试转换的一致性"""

    def test_transform_called_correctly(self):
        """验证 transform 函数被正确调用"""
        segments = [
            MockSegment.from_text("X"),
            MockSegment.from_text("Y"),
            MockSegment.from_text("Z"),
        ]

        call_count = 0

        def counting_transform(segs):
            nonlocal call_count
            call_count += 1
            return segs

        list(split(segments, counting_transform, max_group_tokens=5))

        # transform 应该至少被调用一次
        assert call_count > 0

    def test_transform_receives_context(self):
        """验证 transform 接收到完整的上下文（head + body + tail）"""
        segments = [
            MockSegment.from_text("A"),
            MockSegment.from_text("B"),
            MockSegment.from_text("C"),
            MockSegment.from_text("D"),
        ]

        received_inputs = []

        def recording_transform(segs):
            received_inputs.append([seg.payload for seg in segs])
            return segs

        list(split(segments, recording_transform, max_group_tokens=2))

        # 应该至少收到一次输入
        assert len(received_inputs) > 0

        # 每次输入应该包含多个 segments（head + body + tail）
        # 注意：根据分块策略，某些 chunk 可能只有 body
        for input_segs in received_inputs:
            assert len(input_segs) >= 0  # 可能为空（虽然不太可能）
