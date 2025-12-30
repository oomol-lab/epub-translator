"""快速测试 LLM fill 功能的集成测试"""

import json
import unittest
from pathlib import Path
from xml.etree.ElementTree import fromstring

from epub_translator.llm import LLM
from epub_translator.xml_translator.fill import XMLFill
from epub_translator.xml_translator.text_segment import TextSegment


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

    def _parse_test_case(self, file_path: Path) -> tuple[str, str]:
        """解析测试用例文件，返回 (xml_template, translated_text)"""
        content = file_path.read_text(encoding="utf-8")

        # 文件格式：
        # <xml>...</xml>
        # ```
        # 翻译文本...

        # 找到 ``` 分隔符
        delimiter = "```"
        if delimiter in content:
            parts = content.split(delimiter, 1)
            xml_template = parts[0].strip()
            translated_text = parts[1].strip() if len(parts) > 1 else ""
        else:
            # 如果没有分隔符，整个文件就是 XML
            xml_template = content.strip()
            translated_text = ""

        return xml_template, translated_text

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

        xml_template, translated_text = self._parse_test_case(case_file)
        template_element = fromstring(xml_template)

        # 提取源文本
        source_text = self._extract_source_text(template_element)

        from epub_translator.xml import encode_friendly
        from epub_translator.llm import Message, MessageRole

        # 模拟新的 _fill_into_xml 请求格式
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

        # 验证响应（使用 format 函数）
        from epub_translator.xml_translator.format import format

        try:
            result = format(
                template_ele=template_element,
                validated_text=response,
                errors_limit=10
            )
            print(f"\n✅ Test case '{case_name}' PASSED")
            return result
        except Exception as e:
            print(f"\n❌ Test case '{case_name}' FAILED: {e}")
            print(f"LLM Response:\n{response}")
            raise

    def test_cambridge_toc(self):
        """测试剑桥目录案例（当前失败的案例）"""
        self._test_fill_case("cambridge-toc")


if __name__ == "__main__":
    # 运行单个测试
    unittest.main(verbosity=2)
