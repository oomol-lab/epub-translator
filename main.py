"""
Test script for the Filler class.
This script demonstrates how to use the Filler to fill translated text into XML structure.
"""

import json
import os
import sys
from pathlib import Path
from xml.etree.ElementTree import Element, fromstring

sys.path.append(os.path.abspath(os.path.join(__file__, "..")))

from epub_translator.llm import LLM
from epub_translator.translation.filler import Filler
from epub_translator.xml import encode_friendly


def main() -> None:
    print("=" * 60)
    print("Filler Test - Filling translated text into XML structure")
    print("=" * 60)

    # Read configuration from format.json
    config = _read_format_json()
    print("\n✓ Loaded configuration from format.json")
    print(f"  Model: {config['model']}")

    # Create LLM instance
    llm = LLM(**config, log_dir_path=Path("temp/log"))
    print("✓ Created LLM instance")

    # Create Filler instance
    filler = Filler(llm)
    print("✓ Created Filler instance")

    # Create a test XML structure with nested elements
    source_ele = _create_test_xml()
    print("\n✓ Created test XML structure:")
    print(f"\n{encode_friendly(source_ele)}\n")

    # Translated text (Chinese translation of the English source)
    translated_text = """
西格蒙德·弗洛伊德

“弗洛伊德”和“弗洛伊德式的”重定向至此。其他用法请参见“弗洛伊德式口误”和“弗洛伊德（消歧义）”。

西格蒙德·弗洛伊德[a]（原名西吉斯蒙德·施洛莫·弗洛伊德；1856年5月6日－1939年9月23日）是一位
奥地利神经学家，也是精神分析学的创始人。精神分析学是一种临床方法，通过患者与精神分析师之间的对话
来评估和治疗被认为源于心理冲突的病理[3]，并由此衍生出独特的心理理论和人类能动性理论[4]。

弗洛伊德出生于奥地利帝国摩拉维亚小镇弗赖贝格，父母是加利西亚犹太人。他于1881年在维也纳大学获得
医学博士学位。1885年完成特许任教资格后，他被任命为神经病理学副教授，并于1902年成为
附属教授[7]。弗洛伊德在维也纳生活和工作，他于1886年在那里建立了临床诊所。1938年3月德国吞并
奥地利后，弗洛伊德离开奥地利以躲避纳粹的迫害。他于1939年9月在英国流亡期间去世。
""".strip()

    print(f"✓ Translated text:\n  {translated_text}\n")

    # Fill the translated text into XML structure
    print("→ Calling Filler.fill()...")
    try:
        result = filler.fill(
            source_ele=source_ele,
            translated_text=translated_text,
            on_fail=lambda err: print(f"  ✗ Validation error: {err}"),
        )
        print("\n✓ Successfully filled translated text into XML structure!")
        print("\nResult XML:")
        print(f"\n{encode_friendly(result)}\n")

        # Pretty print the result
        print("=" * 60)
        print("Success! The Filler correctly filled the translated text.")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ Error occurred: {e}")
        import traceback

        traceback.print_exc()


def _create_test_xml() -> Element:
    xml_string = """
<xml>
    <title id="0">Sigmund Freud</title>
    <description id="1">
        "Freud" and "Freudian" redirect here. For other uses, see
        <link id="2">Freudian slip</link> and <bold>Freud</bold>
        (disambiguation).
    </description>
    <p id="3">
        Sigmund Freud[a] (born <bold>Sigismund Schlomo Freud;</bold> 6 May 1856 – 23 September 1939)
        was an Austrian neurologist and the founder of psychoanalysis, a clinical method
        for evaluating and treating pathologies seen as originating from conflicts
        in the psyche, through dialogue between patient and psychoanalyst,<sup>[3]</sup>
        and the distinctive theory of mind and human agency derived from it.<sup>[4]</sup>
    </p>
    <div id="4">
        Freud was born to <link id="5">Galician Jewish parents</link> in the Moravian town of Freiberg,
        in the Austrian Empire. He qualified as a doctor of medicine in 1881
        at the University of Vienna.<sup id="5">[5][6]</sup> Upon completing his habilitation in 1885,
        he was appointed a docent in neuropathology and became an affiliated professor
        in 1902.<sup>[7]</sup> Freud lived and worked in Vienna, having set up his clinical practice
        there in 1886. Following the German annexation of Austria in March 1938, Freud left
        Austria to escape Nazi persecution. He died in exile in the United Kingdom in September 1939.
    </div>
</xml>
""".strip()
    return fromstring(xml_string)


def _read_format_json() -> dict:
    """Read configuration from format.json in the project root."""
    path = Path(__file__).parent / "format.json"
    path = path.resolve()
    with open(path, encoding="utf-8") as file:
        return json.load(file)


if __name__ == "__main__":
    main()
