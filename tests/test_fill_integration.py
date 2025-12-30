"""快速测试 LLM fill 功能的集成测试

注意：这些测试需要调用 LLM，运行时间较长，默认跳过以避免 CI 超时。
如需运行，请使用脚本: python scripts/test_fill_cases.py
或手动运行特定测试: pytest tests/test_fill_integration.py -v -s -k test_cambridge_toc
"""

import json
import unittest
from pathlib import Path
from xml.etree.ElementTree import fromstring

from epub_translator.llm import LLM


class TestFillIntegration(unittest.TestCase):
    """直接测试 LLM fill 功能，用于快速迭代 prompt

    注意：所有测试默认跳过，请使用 scripts/test_fill_cases.py 运行完整测试
    """

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

    def _test_fill_case(self, case_name: str):
        """测试单个 fill 案例（单次请求）"""
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

    @unittest.skip("Skipped in CI - use scripts/test_fill_cases.py instead")
    def test_cambridge_toc(self):
        """测试剑桥目录案例（单次请求，用于快速调试 prompt）"""
        self._test_fill_case("cambridge-toc")

    @unittest.skip("Skipped in CI - use scripts/test_fill_cases.py instead")
    def test_cambridge_toc_2(self):
        """测试剑桥目录案例2（单次请求，用于快速调试 prompt）"""
        self._test_fill_case("cambridge-toc-2")


if __name__ == "__main__":
    # 运行单个测试（手动运行时可以用）
    unittest.main(verbosity=2)

