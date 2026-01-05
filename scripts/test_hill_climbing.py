"""测试 fill 功能的脚本 - 用于验证 prompt 和渐进式锁定系统能否处理困难案例

使用方法:
    python scripts/test_fill_cases.py
    或: .venv/bin/python scripts/test_fill_cases.py
"""

import json
import sys
from pathlib import Path
from xml.etree.ElementTree import Element, fromstring

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))
from epub_translator.llm import LLM, Message, MessageRole
from epub_translator.xml import decode_friendly, encode_friendly
from epub_translator.xml_translator.hill_climbing import HillClimbing
from scripts.utils import read_and_clean_temp


def _extract_xml_element(text: str) -> Element | str:
    """提取 XML 元素，返回 Element 或错误消息字符串"""
    first_xml_element: Element | None = None
    all_xml_elements: int = 0

    for xml_element in decode_friendly(text, tags="xml"):
        if first_xml_element is None:
            first_xml_element = xml_element
        all_xml_elements += 1

    if first_xml_element is None:
        return "No complete <xml>...</xml> block found. Please ensure you have properly closed the XML with </xml> tag."

    if all_xml_elements > 1:
        return (
            f"Found {all_xml_elements} <xml>...</xml> blocks. "
            "Please return only one XML block without any examples or explanations."
        )
    return first_xml_element


def parse_test_case(file_path: Path) -> tuple[str, str, str]:
    """解析测试用例文件，返回 (source_text, xml_template, translated_text)"""
    content = file_path.read_text(encoding="utf-8")

    source_text = ""
    xml_template = ""
    translated_text = ""

    parts = content.split("Source text:", 1)
    if len(parts) > 1:
        rest = parts[1]
        xml_parts = rest.split("XML template:", 1)
        if len(xml_parts) > 1:
            source_text = xml_parts[0].strip()
            trans_parts = xml_parts[1].split("Translated text:", 1)
            if len(trans_parts) > 1:
                xml_section = trans_parts[0].strip()
                xml_start = xml_section.find("```")
                xml_end = xml_section.rfind("```")
                if xml_start != -1 and xml_end != -1 and xml_start < xml_end:
                    xml_content = xml_section[xml_start : xml_end + 3]
                    lines = xml_content.split("\n")
                    xml_template = "\n".join(lines[1:-1])
                translated_text = trans_parts[1].strip()

    return source_text, xml_template, translated_text


def test_fill_case(llm: LLM, case_name: str, case_file: Path, max_retries: int = 10) -> tuple[bool, int, int, float]:
    """
    测试单个 fill 案例（使用爬山算法）

    返回: (success, unused, rounds_used, time_elapsed)
    """
    import time

    from epub_translator.segment import search_text_segments

    start_time = time.time()

    print(f"\n{'=' * 70}")
    print(f"Testing: {case_name}")
    print(f"{'=' * 70}")

    source_text, xml_template, translated_text = parse_test_case(case_file)
    template_element = fromstring(xml_template)

    # 从模板元素创建 TextSegment 列表
    text_segments = list(search_text_segments(template_element))

    # 创建爬山算法实例
    hill_climbing = HillClimbing(
        encoding=llm.encoding,
        request_tag="xml",
        text_segments=text_segments,
        max_fill_displaying_errors=10,
    )

    # 构造初始请求
    request_xml = encode_friendly(hill_climbing.request_element())
    fixed_messages = [
        Message(
            role=MessageRole.SYSTEM,
            message=llm.template("fill").render(),
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

    conversation_history = []

    print(f"Source length: {len(source_text)} chars")
    print(f"Translated length: {len(translated_text)} chars")

    with llm.context() as llm_context:
        did_success: bool = False
        rounds_used: int = max_retries
        for attempt in range(max_retries):
            print(f"\n  Round {attempt + 1}/{max_retries}:", end=" ")

            response = llm_context.request(input=fixed_messages + conversation_history)
            validated_element = _extract_xml_element(response)
            error_message: str | None = None

            if isinstance(validated_element, str):
                error_message = validated_element
                print("XML parse error")
            elif isinstance(validated_element, Element):
                error_message = hill_climbing.submit(validated_element)

            if error_message is None:
                did_success = True
                rounds_used = attempt + 1
                print("Success!")
                break

            print("Has errors")

            conversation_history = [
                Message(role=MessageRole.ASSISTANT, message=response),
                Message(role=MessageRole.USER, message=error_message),
            ]

        elapsed = time.time() - start_time

        if did_success:
            print(f"\n\n  ✅ CONVERGED in {rounds_used} rounds ({elapsed:.1f}s)")
            print(f"{'=' * 70}")
            return True, 0, rounds_used, elapsed
        else:
            print(f"\n\n  ❌ FAILED to converge after {max_retries} rounds ({elapsed:.1f}s)")
            print(f"{'=' * 70}")
            return False, 0, max_retries, elapsed


def main():
    """主函数 - 运行所有测试用例"""
    # 初始化 LLM
    config_path = Path(__file__).parent.parent / "format.json"
    if not config_path.exists():
        print(f"❌ Error: Config file not found: {config_path}")
        return 1

    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    temp_path = read_and_clean_temp()
    llm = LLM(
        **config,
        log_dir_path=temp_path / "logs",
        cache_path=Path(__file__).parent / ".." / "cache",
    )
    # 测试用例目录
    test_cases_dir = Path(__file__).parent.parent / "tests" / "fill" / "request_cases"

    # 定义要测试的案例
    cases = [
        "cambridge-toc",
        "cambridge-toc-2",
    ]

    # 运行所有测试
    results = []
    total_start_time = __import__("time").time()

    print("\n" + "=" * 70)
    print("FILL CASES TEST - Hill Climbing Algorithm Verification")
    print("=" * 70)

    for case_name in cases:
        case_file = test_cases_dir / f"{case_name}.txt"
        if not case_file.exists():
            print(f"\n⚠️  Skipping {case_name}: file not found")
            continue

        success, total_nodes, rounds, elapsed = test_fill_case(llm, case_name, case_file, max_retries=10)
        results.append((case_name, success, total_nodes, rounds, elapsed))

    # 打印总结
    total_elapsed = __import__("time").time() - total_start_time

    print("\n\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, success, _, _, _ in results if success)
    failed = len(results) - passed

    for case_name, success, _, rounds, elapsed in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}  {case_name:30s}  {rounds:2d} rounds  {elapsed:6.1f}s")

    print(f"\n{'-' * 70}")
    print(f"Total: {len(results)} cases  |  Passed: {passed}  |  Failed: {failed}")
    print(f"Total time: {total_elapsed:.1f}s")
    print("=" * 70)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
