import os
import sys

sys.path.append(os.path.abspath(os.path.join(__file__, "..", "..")))

from pathlib import Path
from xml.etree.ElementTree import Element, fromstring

from epub_translator import LLM
from epub_translator.language import CHINESE
from epub_translator.xml import encode_friendly
from epub_translator.xml_translator import XMLStreamMapper, XMLTranslator
from scripts.utils import read_and_clean_temp, read_format_json


def main() -> None:
    print("=" * 60)
    print("Filler Test - Filling translated text into XML structure")
    print("=" * 60)

    # Read configuration from format.json
    config = read_format_json()
    print("\n✓ Loaded configuration from format.json")
    print(f"  Model: {config['model']}")

    # Create LLM instance
    temp_path = read_and_clean_temp()
    llm = LLM(
        **config,
        log_dir_path=temp_path / "logs",
        cache_path=Path(__file__).parent / ".." / "cache",
    )
    print("✓ Created LLM instance")

    # Create Filler instance
    translator = XMLTranslator(
        llm=llm,
        target_language=CHINESE,
        user_prompt=None,
        ignore_translated_error=False,
        max_retries=5,
        max_fill_displaying_errors=10,
        stream_mapper=XMLStreamMapper(
            encoding=llm.encoding,
            max_group_tokens=1200,
        ),
    )
    print("✓ Created Filler instance")

    # Create a test XML structure with nested elements
    source_ele = _create_test_xml()
    print("\n✓ Created test XML structure:")
    print(f"\n{encode_friendly(source_ele)}\n")

    # Fill the translated text into XML structure
    print("→ Calling Filler.fill()...")
    try:
        translated_element = translator.translate_element(source_ele)
        print("\n✓ Successfully filled translated text into XML structure!")
        print("\nResult XML:")
        print(f"\n{encode_friendly(translated_element)}\n")

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
<body>
    Sigmund Freud
    <description>
        "Freud" and "Freudian" redirect here. For other uses, see
        <a>Freudian slip</a> and <strong>Freud</strong>
        (disambiguation).
    </description>
    The main text begins:
    <p class="intro">
        Sigmund Freud[a] (born <strong id="main">Sigismund Schlomo Freud;</strong> 6 May 1856 – 23 September 1939)
        was an Austrian neurologist and the founder of psychoanalysis, a clinical method
        for evaluating and treating pathologies seen as originating from conflicts
        in the psyche, through dialogue between patient and psychoanalyst,<sup>[3]</sup>
        and the distinctive theory of mind and human agency derived from it.<sup>[4]</sup>
    </p>
    <div class="bio">
        Freud was born to <a class="link">Galician Jewish parents</a> in the Moravian town of Freiberg,
        in the Austrian Empire. He qualified as a doctor of medicine in 1881
        at the University of Vienna.<sup>[5][6]</sup> Upon completing his habilitation in 1885,
        he was appointed a docent in neuropathology and became an affiliated professor
        in 1902.<sup>[7]</sup> Freud lived and worked in Vienna, having set up his clinical practice
        there in 1886. Following the German annexation of Austria in March 1938, Freud left
        Austria to escape Nazi persecution. He died in exile in the United Kingdom in September 1939.
    </div>
</body>
""".strip()
    return fromstring(xml_string)


if __name__ == "__main__":
    main()
