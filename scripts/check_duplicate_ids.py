#!/usr/bin/env python3
"""
检测 temp/logs 中日志文件的 XML 模板是否存在重复 ID。

每个 XML 根节点检查一次，因为同一个 XML 可能出现 1-3 次（请求、响应、重试）。
只检查根节点内部的 ID 是否重复。
"""

import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


def extract_xml_blocks(log_content: str) -> list[tuple[str, int, int]]:
    """
    从日志内容中提取所有 XML 代码块

    返回: [(xml_content, start_line, end_line), ...]
    """
    lines = log_content.split("\n")
    blocks = []
    i = 0

    while i < len(lines):
        line = lines[i]
        # 检查是否是 XML 代码块开始
        if re.match(r"```[Xx][Mm][Ll]", line):
            start_line = i + 1  # 行号从 1 开始，且跳过 ```XML 那一行
            xml_lines = []
            i += 1

            # 收集 XML 内容直到遇到 ```
            while i < len(lines):
                if lines[i].strip() == "```":
                    end_line = i  # 结束行号（不包含 ``` 那一行）
                    xml_content = "\n".join(xml_lines)
                    blocks.append((xml_content, start_line + 1, end_line))  # +1 转为 1-based
                    break
                xml_lines.append(lines[i])
                i += 1

        i += 1

    return blocks


def extract_ids_from_xml(xml_string: str) -> list[str]:
    """从 XML 字符串中提取所有 id 属性"""
    try:
        root = ET.fromstring(xml_string)
        ids = []

        # 遍历所有元素（不包括根节点）
        for element in root.iter():
            if element is not root:  # 跳过根节点
                id_value = element.get("id")
                if id_value is not None:
                    ids.append(id_value)

        return ids
    except ET.ParseError as e:
        print(f"  Warning: Failed to parse XML: {e}", file=sys.stderr)
        return []


def check_duplicate_ids(ids: list[str]) -> list[str]:
    """检查 ID 列表中是否有重复，返回重复的 ID"""
    counter = Counter(ids)
    duplicates = [id_val for id_val, count in counter.items() if count > 1]
    return duplicates


def check_log_file(log_file: Path) -> dict[str, Any]:
    """
    检查单个日志文件

    返回格式:
    {
        'file': Path,
        'has_duplicates': bool,
        'xml_blocks': [
            {
                'index': int,
                'start_line': int,
                'end_line': int,
                'duplicate_ids': list[str],
                'id_counts': dict[str, int]
            }
        ]
    }
    """
    result = {"file": log_file, "has_duplicates": False, "xml_blocks": []}

    try:
        content = log_file.read_text(encoding="utf-8")
        xml_blocks = extract_xml_blocks(content)

        # 为了去重，我们跟踪已检查过的 XML 内容
        seen_xmls = set()

        for i, (xml_block, start_line, end_line) in enumerate(xml_blocks):
            # 去重：如果已经检查过这个 XML，跳过
            if xml_block in seen_xmls:
                continue
            seen_xmls.add(xml_block)

            ids = extract_ids_from_xml(xml_block)
            if not ids:
                continue

            duplicates = check_duplicate_ids(ids)
            if duplicates:
                result["has_duplicates"] = True
                counter = Counter(ids)
                result["xml_blocks"].append(
                    {
                        "index": i,
                        "start_line": start_line,
                        "end_line": end_line,
                        "duplicate_ids": duplicates,
                        "id_counts": {id_val: counter[id_val] for id_val in duplicates},
                    }
                )

    except Exception as e:
        print(f"Error reading {log_file}: {e}", file=sys.stderr)

    return result


def main():
    # 获取 temp/logs 目录
    script_dir = Path(__file__).parent
    logs_dir = script_dir.parent / "temp" / "logs"

    if not logs_dir.exists():
        print(f"Error: Logs directory not found: {logs_dir}")
        sys.exit(1)

    # 查找所有 .log 文件
    log_files = sorted(logs_dir.glob("*.log"))

    if not log_files:
        print(f"No log files found in {logs_dir}")
        return

    print(f"Checking {len(log_files)} log files in {logs_dir}...")
    print()

    # 检查每个文件
    total_issues = 0
    problematic_files = []

    for log_file in log_files:
        result = check_log_file(log_file)

        if result["has_duplicates"]:
            total_issues += 1
            problematic_files.append(result)

            for block_info in result["xml_blocks"]:
                # VSCode 可点击格式: file_path:line_start-line_end
                file_location = f"{log_file.absolute()}:{block_info['start_line']}-{block_info['end_line']}"
                print(f"❌ {file_location}")
                print(f"  XML block #{block_info['index']}:")
                for dup_id, count in block_info["id_counts"].items():
                    print(f"    - ID '{dup_id}' appears {count} times")
                print()

    # 总结
    print("=" * 60)
    if total_issues == 0:
        print("✅ No duplicate IDs found in any log files!")
    else:
        print(f"❌ Found duplicate IDs in {total_issues} log file(s)")
    print("=" * 60)

    # 返回非零退出码如果有问题
    sys.exit(1 if total_issues > 0 else 0)


if __name__ == "__main__":
    main()
