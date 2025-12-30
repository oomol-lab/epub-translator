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
  <p><a href="./README.md">English</a> | 中文</p>
</div>


使用大语言模型翻译 EPUB 电子书，同时保留原文。译文与原文并列显示，打造完美的双语阅读体验，特别适合语言学习和对照阅读。

![翻译效果](./docs/images/translation.png)

## 特性

- **双语对照**: 保留原文并与译文并列显示，方便对照阅读
- **AI 驱动**: 利用大语言模型提供高质量、上下文感知的翻译
- **格式保留**: 完整保持 EPUB 结构、样式、图片和格式
- **全面翻译**: 翻译章节内容、目录和元数据
- **进度追踪**: 内置回调函数监控翻译进度
- **灵活的 LLM 支持**: 兼容任何 OpenAI 风格的 API 端点
- **缓存机制**: 内置缓存功能用于翻译失败后恢复进度

## 安装

```bash
pip install epub-translator
```

**系统要求**: Python 3.11、3.12 或 3.13

## 快速开始

### 使用 OOMOL Studio (推荐)

最简单的使用方式是通过 OOMOL Studio 的可视化界面:

[![观看教程](./docs/images/link2youtube.png)](https://www.youtube.com/watch?v=QsAdiskxfXI)

### 使用 Python API

```python
from pathlib import Path
from epub_translator import LLM, translate, language

# 使用 API 凭证初始化 LLM
llm = LLM(
    key="your-api-key",
    url="https://api.openai.com/v1",
    model="gpt-4",
    token_encoding="o200k_base",
)

# 使用语言常量翻译 EPUB 文件
translate(
    llm=llm,
    source_path=Path("source.epub"),
    target_path=Path("translated.epub"),
    target_language=language.CHINESE,
)
```

### 带进度追踪

```python
from tqdm import tqdm

with tqdm(total=100, desc="翻译中", unit="%") as pbar:
    last_progress = 0.0

    def on_progress(progress: float):
        nonlocal last_progress
        increment = (progress - last_progress) * 100
        pbar.update(increment)
        last_progress = progress

    translate(
        llm=llm,
        source_path=Path("source.epub"),
        target_path=Path("translated.epub"),
        target_language="Chinese",
        on_progress=on_progress,
    )
```

## API 参考

### `LLM` 类

初始化翻译所需的 LLM 客户端:

```python
LLM(
    key: str,                          # API 密钥
    url: str,                          # API 端点 URL
    model: str,                        # 模型名称 (例如 "gpt-4")
    token_encoding: str,               # Token 编码方式 (例如 "o200k_base")
    cache_path: PathLike | None = None,           # 缓存目录路径
    timeout: float | None = None,                  # 请求超时时间(秒)
    top_p: float | tuple[float, float] | None = None,
    temperature: float | tuple[float, float] | None = None,
    retry_times: int = 5,                         # 失败重试次数
    retry_interval_seconds: float = 6.0,          # 重试间隔(秒)
    log_dir_path: PathLike | None = None,         # 日志目录路径
)
```

### `translate` 函数

翻译 EPUB 文件:

```python
translate(
    llm: LLM,                          # LLM 实例
    source_path: Path,                 # 源 EPUB 文件路径
    target_path: Path,                 # 输出 EPUB 文件路径
    target_language: str,              # 目标语言 (例如 "Chinese", "English")
    user_prompt: str | None = None,    # 自定义翻译指令
    max_retries: int = 5,              # 翻译失败的最大重试次数
    max_group_tokens: int = 1200,      # 每个翻译组的最大 token 数
    on_progress: Callable[[float], None] | None = None,  # 进度回调函数 (0.0-1.0)
)
```

#### 语言常量

EPUB Translator 提供了预定义的语言常量供用户使用，您可以使用这些常量而不是直接编写语言名称字符串：

```python
from epub_translator import language

# 使用示例：
translate(
    llm=llm,
    source_path=Path("source.epub"),
    target_path=Path("translated.epub"),
    target_language=language.CHINESE,
)

# 您也可以使用自定义的语言字符串：
translate(
    llm=llm,
    source_path=Path("source.epub"),
    target_path=Path("translated.epub"),
    target_language="Icelandic",  # 对于不在常量列表中的语言
)
```

## 配置示例

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

### 其他兼容 OpenAI 的服务

任何提供 OpenAI 兼容 API 的服务都可以使用:

```python
llm = LLM(
    key="your-api-key",
    url="https://your-service.com/v1",
    model="your-model",
    token_encoding="o200k_base",  # 匹配您模型的编码方式
)
```

## 使用场景

- **语言学习**: 阅读原版书籍的同时参考译文
- **学术研究**: 访问外文文献并获得双语参考
- **内容本地化**: 为国际读者准备书籍
- **跨文化阅读**: 在理解文化细微差别的同时欣赏文学作品

## 高级功能

### 自定义翻译提示词

提供特定的翻译指令:

```python
translate(
    llm=llm,
    source_path=Path("source.epub"),
    target_path=Path("translated.epub"),
    target_language="Chinese",
    user_prompt="使用正式语言并保留专业术语",
)
```

### 缓存用于进度恢复

启用缓存以在翻译失败后恢复进度:

```python
llm = LLM(
    key="your-api-key",
    url="https://api.openai.com/v1",
    model="gpt-4",
    token_encoding="o200k_base",
    cache_path="./translation_cache",  # 翻译结果缓存在此
)
```

## 相关项目

### PDF Craft

[PDF Craft](https://github.com/oomol-lab/pdf-craft) 可以将 PDF 文件转换为 EPUB 等多种格式，专注于处理扫描版书籍。将 PDF Craft 与 EPUB Translator 结合使用，可以将扫描版 PDF 书籍转换并翻译成双语 EPUB 格式。

**工作流程**: 扫描版 PDF → [PDF Craft] → EPUB → [EPUB Translator] → 双语 EPUB

完整教程请观看: [将扫描版 PDF 书籍转换为 EPUB 格式并翻译成双语书](https://www.bilibili.com/video/BV1tMQZY5EYY/)

## 贡献

欢迎贡献! 请随时提交 Pull Request。

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 支持

- **问题反馈**: [GitHub Issues](https://github.com/oomol-lab/epub-translator/issues)
- **OOMOL Studio**: [在 OOMOL Studio 中打开](https://hub.oomol.com/package/books-translator?open=true)
