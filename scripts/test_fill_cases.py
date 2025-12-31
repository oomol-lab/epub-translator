"""测试 fill 功能的脚本 - 用于验证 prompt 和渐进式锁定系统能否处理困难案例

使用方法:
    python scripts/test_fill_cases.py
    或: .venv/bin/python scripts/test_fill_cases.py
"""

import json
import sys
from pathlib import Path
from xml.etree.ElementTree import fromstring

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from epub_translator.llm import LLM, Message, MessageRole
from epub_translator.xml import encode_friendly
from epub_translator.xml_translator.format import ValidationError, _extract_xml_element
from epub_translator.xml_translator.progressive_locking import ProgressiveLockingValidator


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
    测试单个 fill 案例（使用渐进式锁定）

    返回: (success, total_nodes, rounds_used, time_elapsed)
    """
    import time

    start_time = time.time()

    print(f"\n{'=' * 70}")
    print(f"Testing: {case_name}")
    print(f"{'=' * 70}")

    source_text, xml_template, translated_text = parse_test_case(case_file)
    template_element = fromstring(xml_template)

    # 构造初始请求
    request_xml = encode_friendly(template_element)
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

    validator = ProgressiveLockingValidator()
    conversation_history = []
    total_nodes = sum(1 for elem in template_element.iter() if elem.get("id") is not None)

    print(f"Total nodes: {total_nodes}")

    with llm.context() as llm_context:
        for attempt in range(max_retries):
            print(f"\n  Round {attempt + 1}/{max_retries}:", end=" ")

            response = llm_context.request(input=fixed_messages + conversation_history)

            try:
                validated_element = _extract_xml_element(response)
                is_complete, error_message, newly_locked = validator.validate_with_locking(
                    template_ele=template_element,
                    validated_ele=validated_element,
                    errors_limit=10,
                )

                locked_count = len(validator.locked_ids)
                print(f"{locked_count}/{total_nodes} nodes locked", end="")

                if newly_locked:
                    print(f" (+{len(newly_locked)})", end="")
                else:
                    print(" (no progress)", end="")

                if is_complete:
                    elapsed = time.time() - start_time
                    print(f"\n\n  ✅ CONVERGED in {attempt + 1} rounds ({elapsed:.1f}s)")
                    print(f"{'=' * 70}")
                    return True, total_nodes, attempt + 1, elapsed

                print()

                # 构造下一轮错误提示
                progress_msg = f"Progress: {locked_count} nodes locked"
                if newly_locked:
                    progress_msg += f", {len(newly_locked)} newly locked this round"
                full_error_message = f"{progress_msg}\n\n{error_message}"

                conversation_history = [
                    Message(role=MessageRole.ASSISTANT, message=response),
                    Message(role=MessageRole.USER, message=full_error_message),
                ]

            except ValidationError as error:
                print("Validation error")
                conversation_history = [
                    Message(role=MessageRole.ASSISTANT, message=response),
                    Message(role=MessageRole.USER, message=str(error)),
                ]

        # 达到最大重试次数仍未收敛
        elapsed = time.time() - start_time
        print(f"\n\n  ❌ FAILED to converge after {max_retries} rounds ({elapsed:.1f}s)")
        print(f"  Final progress: {len(validator.locked_ids)}/{total_nodes} nodes locked")
        print(f"{'=' * 70}")
        return False, total_nodes, max_retries, elapsed


def main():
    """主函数 - 运行所有测试用例"""
    # 初始化 LLM
    config_path = Path(__file__).parent.parent / "format.json"
    if not config_path.exists():
        print(f"❌ Error: Config file not found: {config_path}")
        return 1

    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    llm = LLM(**config)

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
    print("FILL CASES TEST - Progressive Locking System Verification")
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

    for case_name, success, total_nodes, rounds, elapsed in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}  {case_name:30s}  {rounds:2d} rounds  {elapsed:6.1f}s  ({total_nodes} nodes)")

    print(f"\n{'-' * 70}")
    print(f"Total: {len(results)} cases  |  Passed: {passed}  |  Failed: {failed}")
    print(f"Total time: {total_elapsed:.1f}s")
    print("=" * 70)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
