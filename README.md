<div align=center>
  <h1>EPUB Translator</h1>
  <p>
    <a href="https://github.com/oomol-lab/epub-translator/actions/workflows/merge-build.yml" target="_blank"><img src="https://img.shields.io/github/actions/workflow/status/oomol-lab/epub-translator/merge-build.yml" alt="ci" /></a>
    <a href="https://pypi.org/project/epub-translator/" target="_blank"><img src="https://img.shields.io/badge/pip_install-epub--translator-blue" alt="pip install epub-translator" /></a>
    <a href="https://pypi.org/project/epub-translator/" target="_blank"><img src="https://img.shields.io/pypi/v/epub-translator.svg" alt="pypi epub-translator" /></a>
    <a href="https://pypi.org/project/epub-translator/" target="_blank"><img src="https://img.shields.io/pypi/pyversions/epub-translator.svg" alt="python versions" /></a>
    <a href="https://github.com/oomol-lab/epub-translator/blob/main/LICENSE" target="_blank"><img src="https://img.shields.io/github/license/oomol-lab/epub-translator" alt="license" /></a>
  </p>
  <p><a href="https://hub.oomol.com/package/books-translator?open=true" target="_blank"><img src="https://static.oomol.com/assets/button.svg" alt="Open in OOMOL Studio" /></a></p>
  <p>English | <a href="./README_zh-CN.md">中文</a></p>
</div>


Translate EPUB books using Large Language Models while preserving the original text. The translated content is displayed side-by-side with the original, creating bilingual books perfect for language learning and cross-reference reading.

![Translation Effect](./docs/images/translation.png)

## Features

- **Bilingual Output**: Preserves original text alongside translations for easy comparison
- **LLM-Powered**: Leverages large language models for high-quality, context-aware translations
- **Format Preservation**: Maintains EPUB structure, styles, images, and formatting
- **Complete Translation**: Translates chapter content, table of contents, and metadata
- **Progress Tracking**: Monitor translation progress with built-in callbacks
- **Flexible LLM Support**: Works with any OpenAI-compatible API endpoint
- **Caching**: Built-in caching for progress recovery when translation fails

## Installation

```bash
pip install epub-translator
```

**Requirements**: Python 3.11, 3.12, or 3.13

## Quick Start

### Using OOMOL Studio (Recommended)

The easiest way to use EPUB Translator is through OOMOL Studio with a visual interface:

[![Watch the Tutorial](./docs/images/link2youtube.png)](https://www.youtube.com/watch?v=QsAdiskxfXI)

### Using Python API

```python
from epub_translator import LLM, translate, language, SubmitKind

# Initialize LLM with your API credentials
llm = LLM(
    key="your-api-key",
    url="https://api.openai.com/v1",
    model="gpt-4",
    token_encoding="o200k_base",
)

# Translate EPUB file using language constants
translate(
    source_path="source.epub",
    target_path="translated.epub",
    target_language=language.ENGLISH,
    submit=SubmitKind.APPEND_BLOCK,
    llm=llm,
)
```

### With Progress Tracking

```python
from tqdm import tqdm

with tqdm(total=100, desc="Translating", unit="%") as pbar:
    last_progress = 0.0

    def on_progress(progress: float):
        nonlocal last_progress
        increment = (progress - last_progress) * 100
        pbar.update(increment)
        last_progress = progress

    translate(
        source_path="source.epub",
        target_path="translated.epub",
        target_language="English",
        submit=SubmitKind.APPEND_BLOCK,
        llm=llm,
        on_progress=on_progress,
    )
```

## API Reference

### `LLM` Class

Initialize the LLM client for translation:

```python
LLM(
    key: str,                          # API key
    url: str,                          # API endpoint URL
    model: str,                        # Model name (e.g., "gpt-4")
    token_encoding: str,               # Token encoding (e.g., "o200k_base")
    cache_path: PathLike | None = None,           # Cache directory path
    timeout: float | None = None,                  # Request timeout in seconds
    top_p: float | tuple[float, float] | None = None,
    temperature: float | tuple[float, float] | None = None,
    retry_times: int = 5,                         # Number of retries on failure
    retry_interval_seconds: float = 6.0,          # Interval between retries
    log_dir_path: PathLike | None = None,         # Log directory path
)
```

### `translate` Function

Translate an EPUB file:

```python
translate(
    source_path: PathLike | str,       # Source EPUB file path
    target_path: PathLike | str,       # Output EPUB file path
    target_language: str,              # Target language (e.g., "English", "Chinese")
    submit: SubmitKind,                # How to insert translations (REPLACE, APPEND_TEXT, or APPEND_BLOCK)
    user_prompt: str | None = None,    # Custom translation instructions
    max_retries: int = 5,              # Maximum retries for failed translations
    max_group_tokens: int = 1200,      # Maximum tokens per translation group
    llm: LLM | None = None,            # Single LLM instance for both translation and filling
    translation_llm: LLM | None = None,  # LLM instance for translation (overrides llm)
    fill_llm: LLM | None = None,       # LLM instance for XML filling (overrides llm)
    on_progress: Callable[[float], None] | None = None,  # Progress callback (0.0-1.0)
    on_fill_failed: Callable[[FillFailedEvent], None] | None = None,  # Error callback
)
```

**Note**: Either `llm` or both `translation_llm` and `fill_llm` must be provided. Using separate LLMs allows for task-specific optimization.

#### Submit Modes

The `submit` parameter controls how translated content is inserted into the document. Use `SubmitKind` enum to specify the insertion mode:

```python
from epub_translator import SubmitKind

# Three available modes:
# - SubmitKind.REPLACE: Replace original content with translation (single-language output)
# - SubmitKind.APPEND_TEXT: Append translation as inline text (bilingual output)
# - SubmitKind.APPEND_BLOCK: Append translation as block elements (bilingual output, recommended)
```

**Mode Comparison:**

- **`SubmitKind.REPLACE`**: Creates a single-language translation by replacing original text with translated content. Useful for creating books in the target language only.

- **`SubmitKind.APPEND_TEXT`**: Appends translations as inline text immediately after the original content. Both languages appear in the same paragraph, creating a continuous reading flow.

- **`SubmitKind.APPEND_BLOCK`** (Recommended): Appends translations as separate block elements (paragraphs) after the original. This creates clear visual separation between languages, making it ideal for side-by-side bilingual reading.

**Example:**

```python
# For bilingual books (recommended)
translate(
    source_path="source.epub",
    target_path="translated.epub",
    target_language=language.ENGLISH,
    submit=SubmitKind.APPEND_BLOCK,
    llm=llm,
)

# For single-language translation
translate(
    source_path="source.epub",
    target_path="translated.epub",
    target_language=language.ENGLISH,
    submit=SubmitKind.REPLACE,
    llm=llm,
)
```

#### Language Constants

EPUB Translator provides predefined language constants for convenience. You can use these constants instead of writing language names as strings:

```python
from epub_translator import language

# Usage example:
translate(
    source_path="source.epub",
    target_path="translated.epub",
    target_language=language.ENGLISH,
    submit=SubmitKind.APPEND_BLOCK,
    llm=llm,
)

# You can also use custom language strings:
translate(
    source_path="source.epub",
    target_path="translated.epub",
    target_language="Icelandic",  # For languages not in the constants
    submit=SubmitKind.APPEND_BLOCK,
    llm=llm,
)
```

### Error Handling with `on_fill_failed`

Monitor translation errors using the `on_fill_failed` callback. The system automatically retries failed translations up to `max_retries` times (default: 5). Most errors are recovered during retries and don't affect the final output.

```python
from epub_translator import FillFailedEvent

def handle_fill_error(event: FillFailedEvent):
    # Only log critical errors that will affect the final EPUB
    if event.over_maximum_retries:
        print(f"Critical error after {event.retried_count} attempts:")
        print(f"  {event.error_message}")
        print("  This error will be present in the final EPUB file!")

translate(
    source_path="source.epub",
    target_path="translated.epub",
    target_language=language.ENGLISH,
    submit=SubmitKind.APPEND_BLOCK,
    llm=llm,
    on_fill_failed=handle_fill_error,
)
```

**Understanding Error Severity:**

The `FillFailedEvent` contains:
- `error_message: str` - Description of the error
- `retried_count: int` - Current retry attempt number (1 to max_retries)
- `over_maximum_retries: bool` - Whether the error is critical

**Error Categories:**

- **Recoverable errors** (`over_maximum_retries=False`): Errors during retry attempts. The system will continue retrying and may resolve these automatically. Safe to ignore in most cases.

- **Critical errors** (`over_maximum_retries=True`): Errors that persist after all retry attempts. These will appear in the final EPUB file and should be investigated.

**Advanced Usage:**

For verbose logging during translation debugging:

```python
def handle_fill_error(event: FillFailedEvent):
    if event.over_maximum_retries:
        # Critical: affects final output
        print(f"❌ CRITICAL: {event.error_message}")
    else:
        # Informational: system is retrying
        print(f"⚠️  Retry {event.retried_count}: {event.error_message}")
```

### Dual-LLM Architecture

Use separate LLM instances for translation and XML structure filling with different optimization parameters:

```python
# Create two LLM instances with different temperatures
translation_llm = LLM(
    key="your-api-key",
    url="https://api.openai.com/v1",
    model="gpt-4",
    token_encoding="o200k_base",
    temperature=0.8,  # Higher temperature for creative translation
)

fill_llm = LLM(
    key="your-api-key",
    url="https://api.openai.com/v1",
    model="gpt-4",
    token_encoding="o200k_base",
    temperature=0.3,  # Lower temperature for structure preservation
)

translate(
    source_path="source.epub",
    target_path="translated.epub",
    target_language=language.ENGLISH,
    submit=SubmitKind.APPEND_BLOCK,
    translation_llm=translation_llm,
    fill_llm=fill_llm,
)
```

## Configuration Examples

### OpenAI

```python
llm = LLM(
    key="sk-...",
    url="https://api.openai.com/v1",
    model="gpt-4",
    token_encoding="o200k_base",
)
```

### Azure OpenAI

```python
llm = LLM(
    key="your-azure-key",
    url="https://your-resource.openai.azure.com/openai/deployments/your-deployment",
    model="gpt-4",
    token_encoding="o200k_base",
)
```

### Other OpenAI-Compatible Services

Any service with an OpenAI-compatible API can be used:

```python
llm = LLM(
    key="your-api-key",
    url="https://your-service.com/v1",
    model="your-model",
    token_encoding="o200k_base",  # Match your model's encoding
)
```

## Use Cases

- **Language Learning**: Read books in their original language with side-by-side translations
- **Academic Research**: Access foreign literature with bilingual references
- **Content Localization**: Prepare books for international audiences
- **Cross-Cultural Reading**: Enjoy literature while understanding cultural nuances

## Advanced Features

### Custom Translation Prompts

Provide specific translation instructions:

```python
translate(
    source_path="source.epub",
    target_path="translated.epub",
    target_language="English",
    submit=SubmitKind.APPEND_BLOCK,
    llm=llm,
    user_prompt="Use formal language and preserve technical terminology",
)
```

### Caching for Progress Recovery

Enable caching to resume translation progress after failures:

```python
llm = LLM(
    key="your-api-key",
    url="https://api.openai.com/v1",
    model="gpt-4",
    token_encoding="o200k_base",
    cache_path="./translation_cache",  # Translations are cached here
)
```

## Related Projects

### PDF Craft

[PDF Craft](https://github.com/oomol-lab/pdf-craft) converts PDF files into EPUB and other formats, with a focus on scanned books. Combine PDF Craft with EPUB Translator to convert and translate scanned PDF books into bilingual EPUB format.

**Workflow**: Scanned PDF → [PDF Craft] → EPUB → [EPUB Translator] → Bilingual EPUB

For a complete tutorial, watch: [Convert scanned PDF books to EPUB format and translate them into bilingual books](https://www.bilibili.com/video/BV1tMQZY5EYY/)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/oomol-lab/epub-translator/issues)
- **OOMOL Studio**: [Open in OOMOL Studio](https://hub.oomol.com/package/books-translator?open=true)
