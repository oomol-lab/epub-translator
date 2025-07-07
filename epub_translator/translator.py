from os import PathLike
from pathlib import Path
from tempfile import mkdtemp
from shutil import rmtree

from .llm import LLM
from .epub import HTMLFile
from .zip_context import ZipContext
from .translation import translate as _translate, Fragment, Incision, Language, ProgressReporter


def translate(
      llm: LLM,
      source_path: PathLike,
      translated_path: PathLike,
      target_language: Language,
      user_prompt: str | None = None,
      working_path: PathLike | None = None,
      max_chunk_tokens_count: int = 3000,
      max_threads_count: int = 1,
      report_progress: ProgressReporter | None = None,
    ) -> None:

  source_path = Path(source_path)
  translated_path = Path(translated_path)
  working_path = Path(working_path) if working_path else None
  report_progress = report_progress or (lambda _: None)

  _Translator(
    llm=llm,
    target_language=target_language,
    user_prompt=user_prompt,
    max_chunk_tokens_count=max_chunk_tokens_count,
    max_threads_count=max_threads_count,
    report_progress=report_progress,
  ).do(
    source_path=source_path,
    translated_path=translated_path,
    working_path=working_path,
  )

class _Translator:
  def __init__(
        self,
        llm: LLM,
        target_language: Language,
        user_prompt: str | None,
        max_chunk_tokens_count: int,
        max_threads_count: int,
        report_progress: ProgressReporter,
      ) -> None:

    self._llm: LLM = llm
    self._target_language: Language = target_language
    self._user_prompt: str | None = user_prompt
    self._max_chunk_tokens_count: int = max_chunk_tokens_count
    self._max_threads_count: int = max_threads_count
    self._report_progress: ProgressReporter = report_progress

  def do(self, source_path: Path, translated_path: Path, working_path: Path | None) -> None:
    is_temp_workspace = not bool(working_path)
    working_path = working_path or Path(mkdtemp())
    try:
      temp_dir = _clean_path(working_path / "temp")
      temp_dir.mkdir(parents=True, exist_ok=True)
      cache_path = working_path / "cache"

      context = ZipContext(
        epub_path=Path(source_path),
        temp_dir=temp_dir,
      )
      context.replace_ncx(lambda texts: self._translate_ncx(
        texts=texts,
        cache_path=cache_path,
        report_progress=lambda p: self._report_progress(p * 0.1)),
      )
      self._translate_spine(
        context=context,
        cache_path=cache_path,
        report_progress=lambda p: self._report_progress(0.1 + p * 0.8),
      )
      context.archive(translated_path)
      self._report_progress(1.0)

    finally:
      if is_temp_workspace:
        rmtree(working_path, ignore_errors=True)

  def _translate_ncx(self, texts: list[str], cache_path: Path, report_progress: ProgressReporter) -> list[str]:
    return list(_translate(
      llm=self._llm,
      cache_path=cache_path,
      max_chunk_tokens_count=self._max_chunk_tokens_count,
      max_threads_count=1,
      target_language=self._target_language,
      user_prompt=self._user_prompt,
      report_progress=report_progress,
      gen_fragments_iter=lambda: (
        Fragment(
          text=text,
          start_incision=Incision.IMPOSSIBLE,
          end_incision=Incision.IMPOSSIBLE,
        )
        for text in texts
      ),
    ))

  def _translate_spine(self, context: ZipContext, cache_path: Path, report_progress: ProgressReporter):
    spine_paths_iter = iter(list(context.search_spine_paths()))
    spine_file: HTMLFile | None = None
    translated_texts: list[str] = []
    translated_count: int = 0

    for translated_text in _translate(
      llm=self._llm,
      gen_fragments_iter=lambda: _gen_fragments(context),
      cache_path=cache_path,
      max_chunk_tokens_count=self._max_chunk_tokens_count,
      max_threads_count=self._max_threads_count,
      target_language=self._target_language,
      user_prompt=self._user_prompt,
      report_progress=report_progress,
    ):
      did_touch_end = False

      if spine_file is not None and \
        translated_count >= len(translated_texts):
        spine_file.write_texts(translated_texts)
        spine_file = None

      while spine_file is None:
        spine_path = next(spine_paths_iter, None)
        if spine_path is None:
          did_touch_end = True
          break
        spine_file = context.read_spine_file(spine_path)
        if spine_file.texts_length == 0:
          spine_file = None
          continue
        translated_texts = [""] * spine_file.texts_length
        translated_count = 0

      translated_texts[translated_count] = translated_text
      translated_count += 1

      if did_touch_end:
        break
    if spine_file and translated_count > 0:
      spine_file.write_texts(translated_texts)

    context.write_spine_file(spine_path, spine_file)

def _gen_fragments(context: ZipContext):
  for spine_path in context.search_spine_paths():
    spine_file = context.read_spine_file(spine_path)
    for text in spine_file.read_texts():
      yield Fragment(
        text=text,
        start_incision=Incision.IMPOSSIBLE,
        end_incision=Incision.IMPOSSIBLE,
      )

def _clean_path(path: Path) -> Path:
  if path.exists():
    if path.is_file():
      path.unlink()
    elif path.is_dir():
      rmtree(path, ignore_errors=True)
  return path