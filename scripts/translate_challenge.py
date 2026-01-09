import os
import re
import sys
from pathlib import Path
from xml.etree.ElementTree import Element

sys.path.append(os.path.abspath(os.path.join(__file__, "..", "..")))

from epub_translator.llm import Message, MessageRole
from epub_translator.segment import BlockSegment, search_inline_segments, search_text_segments
from epub_translator.xml import decode_friendly
from epub_translator.xml_translator.hill_climbing import HillClimbing
from scripts.utils import load_llm, read_and_clean_temp


def test_challenge_file(file_path: Path, fill_llm, max_retries: int = 5) -> dict:
    """Test a single challenge file with hill climbing validation."""
    print(f"\n{'=' * 80}")
    print(f"Testing: {file_path.name}")
    print(f"{'=' * 80}\n")

    # Read challenge file
    with open(file_path, encoding="utf-8") as f:
        user_message = f.read()

    # Extract XML template for creating BlockSegment
    xml_template = extract_xml_template(user_message)
    if xml_template is None:
        print("❌ Failed to extract XML template")
        return {
            "file": file_path.name,
            "success": False,
            "retries": 0,
            "error_message": "Failed to extract XML template",
        }

    # Parse XML template to create BlockSegment
    try:
        # Use decode_friendly to get the template element
        template_element = None
        for elem in decode_friendly(xml_template, tags="xml"):
            template_element = elem
            break

        if template_element is None:
            raise ValueError("No XML element found in template")

        # Create BlockSegment from template
        text_segments = list(search_text_segments(template_element))
        inline_segments = list(search_inline_segments(text_segments))
        block_segment = BlockSegment(
            root_tag="xml",
            inline_segments=inline_segments,
        )
    except Exception as e:
        print(f"❌ Failed to parse XML template: {e}")
        return {
            "file": file_path.name,
            "success": False,
            "retries": 0,
            "error_message": f"Failed to parse XML template: {str(e)}",
        }

    # Initialize HillClimbing
    hill_climbing = HillClimbing(
        encoding=fill_llm.encoding,
        max_fill_displaying_errors=5,
        block_segment=block_segment,
    )

    # Create fixed messages
    fixed_messages = [
        Message(
            role=MessageRole.SYSTEM,
            message=fill_llm.template("fill").render(),
        ),
        Message(
            role=MessageRole.USER,
            message=user_message,
        ),
    ]
    conversation_history = []

    result = {
        "file": file_path.name,
        "success": False,
        "retries": 0,
        "error_message": None,
    }

    with fill_llm.context() as llm_context:
        error_message = None

        for retry_count in range(max_retries):
            print(f"Attempt {retry_count + 1}/{max_retries}...")

            try:
                response = llm_context.request(fixed_messages + conversation_history)
                validated_element = extract_xml_element(response)
                error_message = None

                if isinstance(validated_element, str):
                    error_message = validated_element
                elif isinstance(validated_element, Element):
                    # Use hill climbing to validate
                    error_message = hill_climbing.submit(validated_element)

                if error_message is None:
                    print(f"✅ Success on attempt {retry_count + 1}")
                    result["success"] = True
                    result["retries"] = retry_count + 1
                    break

                print(f"❌ Failed:\n{error_message}\n\n")

                # Add to conversation history for next retry
                conversation_history = [
                    Message(role=MessageRole.ASSISTANT, message=response),
                    Message(role=MessageRole.USER, message=error_message),
                ]
                result["retries"] = retry_count + 1
                result["error_message"] = error_message

            except Exception as e:
                error_message = f"Exception: {str(e)}"
                print(f"❌ Exception: {e}\n\n")
                result["retries"] = retry_count + 1
                result["error_message"] = error_message
                break

        if not result["success"]:
            print("\n⚠️  Maximum retries reached without success")
            if error_message:
                print(f"Last error: {error_message}")

    return result


def extract_xml_template(content: str) -> str | None:
    """Extract XML template from challenge file content."""
    xml_match = re.search(r"XML template:\n```XML\n(.*?)\n```", content, re.DOTALL)
    if not xml_match:
        return None
    return xml_match.group(1).strip()


def extract_xml_element(response: str) -> Element | str:
    """Extract and parse XML from LLM response."""
    xml_match = re.search(r"```[xX]?[mM]?[lL]?\s*\n(.*?)\n```", response, re.DOTALL)
    if xml_match:
        xml_content = xml_match.group(1)
    else:
        xml_match = re.search(r"<xml>.*?</xml>", response, re.DOTALL)
        if xml_match:
            xml_content = xml_match.group(0)
        else:
            return "Failed to extract XML from response"

    try:
        # Use decode_friendly to parse XML
        for element in decode_friendly(xml_content, tags="xml"):
            return element
        return "No XML element found after decoding"
    except Exception as e:
        return f"XML parsing error: {str(e)}"


def main() -> None:
    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(description="Test challenge files for epub-translator")
    parser.add_argument(
        "prefixes",
        nargs="*",
        help="Optional prefix(es) to filter test files (e.g., 'case2' or 'case1 case2')",
    )
    args = parser.parse_args()

    challenge_dir = Path(__file__).parent / ".." / "tests" / "challenge"
    temp_path = read_and_clean_temp()

    # Load LLM
    print("Loading LLM...")
    _, fill_llm = load_llm(
        cache_path=Path(__file__).parent / ".." / "cache",
        log_dir_path=temp_path / "logs",
    )

    # Find all challenge files
    all_files = sorted(challenge_dir.glob("case*.txt"))

    # Filter by prefixes if provided
    if args.prefixes:
        challenge_files = []
        for f in all_files:
            if any(f.stem.startswith(prefix) for prefix in args.prefixes):
                challenge_files.append(f)

        if not challenge_files:
            print(f"No challenge files found matching prefixes: {', '.join(args.prefixes)}")
            print(f"Available files: {', '.join(f.stem for f in all_files)}")
            return
        print(f"\nFiltered by prefixes: {', '.join(args.prefixes)}")
    else:
        challenge_files = all_files

    if not challenge_files:
        print(f"No challenge files found in {challenge_dir}")
        return

    print(f"Found {len(challenge_files)} challenge file(s) to test")
    print(f"Challenge directory: {challenge_dir}")

    # Test each file
    results = []
    for challenge_file in challenge_files:
        result = test_challenge_file(challenge_file, fill_llm, max_retries=5)
        results.append(result)

    # Print summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}\n")

    success_count = sum(1 for r in results if r["success"])
    total_count = len(results)

    print(f"Total tests: {total_count}")
    print(f"Successful: {success_count} ({success_count / total_count * 100:.1f}%)")
    print(f"Failed: {total_count - success_count} ({(total_count - success_count) / total_count * 100:.1f}%)")
    print()

    # Detailed results
    print("Detailed Results:")
    print("-" * 80)
    for result in results:
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        print(f"{status} | {result['file']:40s} | Retries: {result['retries']}")
        if not result["success"] and result["error_message"]:
            error_preview = result["error_message"][:100].replace("\n", " ")
            print(f"       Error: {error_preview}...")
    print()

    # Statistics by retry count
    retry_stats = {}
    for result in results:
        if result["success"]:
            retries = result["retries"]
            retry_stats[retries] = retry_stats.get(retries, 0) + 1

    if retry_stats:
        print("Success by Retry Count:")
        print("-" * 80)
        for retry_count in sorted(retry_stats.keys()):
            count = retry_stats[retry_count]
            print(f"  {retry_count} retries: {count} tests")


if __name__ == "__main__":
    main()
