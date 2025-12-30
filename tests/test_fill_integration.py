"""快速测试 LLM fill 功能的集成测试"""

import json
import unittest
from pathlib import Path
from xml.etree.ElementTree import fromstring

from epub_translator.llm import LLM


class TestFillIntegration(unittest.TestCase):
    """直接测试 LLM fill 功能，用于快速迭代 prompt"""

    @classmethod
    def setUpClass(cls):
        """初始化 LLM（只初始化一次）"""
        config_path = Path(__file__).parent.parent / "format.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

        cls.llm = LLM(**config)
        cls.test_cases_dir = Path(__file__).parent / "fill" / "request_cases"

    def _parse_test_case(self, file_path: Path) -> tuple[str, str, str]:
        """解析测试用例文件，返回 (source_text, xml_template, translated_text)

        文件格式：
        Source text:
        ...
        XML template:
        ```XML
        ...
        ```
        Translated text:
        ...
        """
        content = file_path.read_text(encoding="utf-8")

        source_text = ""
        xml_template = ""
        translated_text = ""

        # 提取各个部分
        parts = content.split("Source text:", 1)
        if len(parts) > 1:
            rest = parts[1]
            xml_parts = rest.split("XML template:", 1)
            if len(xml_parts) > 1:
                source_text = xml_parts[0].strip()
                trans_parts = xml_parts[1].split("Translated text:", 1)
                if len(trans_parts) > 1:
                    xml_section = trans_parts[0].strip()
                    # 提取 ```XML ... ``` 中的内容
                    xml_start = xml_section.find("```")
                    xml_end = xml_section.rfind("```")
                    if xml_start != -1 and xml_end != -1 and xml_start < xml_end:
                        # Skip the first line (```XML or ```xml)
                        xml_content = xml_section[xml_start : xml_end + 3]
                        lines = xml_content.split("\n")
                        xml_template = "\n".join(lines[1:-1])
                    translated_text = trans_parts[1].strip()

        return source_text, xml_template, translated_text

    def _extract_source_text(self, element) -> str:
        """从 XML 元素中提取源文本"""
        # 简单方法：遍历所有带有 id 的元素，提取它们的文本内容
        texts = []

        def extract_text(elem):
            # 提取元素的直接文本
            if elem.text and elem.text.strip():
                texts.append(elem.text.strip())
            # 递归处理子元素
            for child in elem:
                extract_text(child)
                # 提取子元素的 tail 文本
                if child.tail and child.tail.strip():
                    texts.append(child.tail.strip())

        extract_text(element)
        return "\n\n".join(texts)

    def _test_fill_case(self, case_name: str):
        """测试单个 fill 案例"""
        case_file = self.test_cases_dir / f"{case_name}.txt"
        if not case_file.exists():
            self.skipTest(f"Test case file not found: {case_file}")

        source_text, xml_template, translated_text = self._parse_test_case(case_file)
        template_element = fromstring(xml_template)

        from epub_translator.llm import Message, MessageRole
        from epub_translator.xml import encode_friendly

        # 构造 LLM 请求
        request_xml = encode_friendly(template_element)
        user_message = (
            f"Source text:\n{source_text}\n\n"
            f"XML template:\n```XML\n{request_xml}\n```\n\n"
            f"Translated text:\n{translated_text}"
        )

        messages = [
            Message(
                role=MessageRole.SYSTEM,
                message=self.llm.template("fill").render(),
            ),
            Message(
                role=MessageRole.USER,
                message=user_message,
            ),
        ]

        # 发送请求
        response = self.llm.request(input=messages)

        # 验证响应
        from epub_translator.xml_translator.format import format

        try:
            result = format(template_ele=template_element, validated_text=response, errors_limit=10)
            print(f"\n✅ Test case '{case_name}' PASSED")
            return result
        except Exception as e:
            print(f"\n❌ Test case '{case_name}' FAILED: {e}")
            print(f"LLM Response:\n{response}")
            raise

    def _test_fill_case_with_progressive_locking(self, case_name: str, max_retries: int = 10):
        """测试单个 fill 案例（使用渐进式锁定，允许多轮迭代）"""
        case_file = self.test_cases_dir / f"{case_name}.txt"
        if not case_file.exists():
            self.skipTest(f"Test case file not found: {case_file}")

        source_text, xml_template, translated_text = self._parse_test_case(case_file)
        template_element = fromstring(xml_template)

        from epub_translator.llm import Message, MessageRole
        from epub_translator.xml import encode_friendly
        from epub_translator.xml_translator.format import ValidationError, _extract_xml_element
        from epub_translator.xml_translator.progressive_locking import ProgressiveLockingValidator

        # 构造初始请求
        request_xml = encode_friendly(template_element)
        fixed_messages = [
            Message(
                role=MessageRole.SYSTEM,
                message=self.llm.template("fill").render(),
            ),
            Message(
                role=MessageRole.USER,
                message=(
                    f"Source text:\n{source_text}\n\n"
                    f"XML template:\n```XML\n{request_xml}\n```\n\n"
                    f"Translated text:\n{translated_text}"
                ),
            ),
        ]

        validator = ProgressiveLockingValidator()
        conversation_history = []
        total_nodes = sum(1 for elem in template_element.iter() if elem.get("id") is not None)

        print(f"\n{'=' * 60}")
        print(f"Testing '{case_name}' with progressive locking")
        print(f"Total nodes: {total_nodes}")
        print(f"{'=' * 60}")

        for attempt in range(max_retries):
            print(f"\n--- Round {attempt + 1}/{max_retries} ---")

            response = self.llm.request(input=fixed_messages + conversation_history)

            try:
                validated_element = _extract_xml_element(response)
                is_complete, error_message, newly_locked = validator.validate_with_locking(
                    template_ele=template_element,
                    validated_ele=validated_element,
                    errors_limit=10,
                )

                print(f"Locked: {len(validator.locked_ids)}/{total_nodes} nodes", end="")
                if newly_locked:
                    print(f" (+{len(newly_locked)} this round)")
                else:
                    print(" (no progress)")

                if is_complete:
                    print(f"\n{'=' * 60}")
                    print(f"✅ Test case '{case_name}' CONVERGED in {attempt + 1} rounds")
                    print(f"{'=' * 60}")
                    return validated_element

                # 构造下一轮的错误提示
                progress_msg = f"Progress: {len(validator.locked_ids)} nodes locked"
                if newly_locked:
                    progress_msg += f", {len(newly_locked)} newly locked this round"
                full_error_message = f"{progress_msg}\n\n{error_message}"

                print(f"Errors: {error_message[:100]}...")

                conversation_history = [
                    Message(role=MessageRole.ASSISTANT, message=response),
                    Message(role=MessageRole.USER, message=full_error_message),
                ]

            except ValidationError as error:
                print(f"Validation error: {error}")
                conversation_history = [
                    Message(role=MessageRole.ASSISTANT, message=response),
                    Message(role=MessageRole.USER, message=str(error)),
                ]

        # 达到最大重试次数
        print(f"\n{'=' * 60}")
        print(f"❌ Test case '{case_name}' FAILED to converge after {max_retries} rounds")
        print(f"Final progress: {len(validator.locked_ids)}/{total_nodes} nodes locked")
        print(f"{'=' * 60}")
        self.fail(f"Failed to converge after {max_retries} attempts")

    def test_cambridge_toc(self):
        """测试剑桥目录案例（单次请求，用于快速调试 prompt）"""
        self._test_fill_case("cambridge-toc")

    def test_cambridge_toc_2(self):
        """测试剑桥目录案例2（单次请求，用于快速调试 prompt）"""
        self._test_fill_case("cambridge-toc-2")

    def test_cambridge_toc_progressive(self):
        """测试剑桥目录案例（渐进式锁定，允许多轮迭代）"""
        self._test_fill_case_with_progressive_locking("cambridge-toc", max_retries=10)

    def test_cambridge_toc_2_progressive(self):
        """测试剑桥目录案例2（渐进式锁定，允许多轮迭代）"""
        self._test_fill_case_with_progressive_locking("cambridge-toc-2", max_retries=10)


if __name__ == "__main__":
    # 运行单个测试
    unittest.main(verbosity=2)
