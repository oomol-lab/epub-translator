from os import PathLike
from pathlib import Path
from tempfile import mkdtemp
from shutil import rmtree

from .llm import LLM
from .epub import HTMLFile
from .zip_context import ZipContext
from .translation import translate as _translate, Fragment, Incision


def translate(
      llm: LLM,
      source_path: PathLike,
      translated_path: PathLike,
      working_path: PathLike | None = None,
    ):

  is_temp_workspace = not bool(working_path)
  working_path = working_path or mkdtemp()
  try:
    temp_dir = _clean_path(Path(working_path) / "temp")
    temp_dir.mkdir(parents=True, exist_ok=True)

    context = ZipContext(
      epub_path=Path(source_path),
      temp_dir=temp_dir,
    )
    context.replace_ncx(lambda texts: _translate_ncx(llm, texts))
    _translate_spine(llm, context, working_path)

    translated_path = _clean_path(Path(translated_path))
    translated_path.parent.mkdir(parents=True, exist_ok=True)
    context.archive(translated_path)

  finally:
    if is_temp_workspace:
      rmtree(working_path, ignore_errors=True)

def _translate_ncx(llm: LLM, texts: list[str]) -> list[str]:
  return list(_translate(
    llm=llm,
    cache_path=None,
    max_chunk_tokens_count=4096,
    gen_fragments_iter=lambda: (
      Fragment(
        text=text,
        start_incision=Incision.IMPOSSIBLE,
        end_incision=Incision.IMPOSSIBLE,
      )
      for text in texts
    ),
  ))

def _translate_spine(llm: LLM, context: ZipContext, working_path: Path):
  spine_paths_iter = iter(list(context.search_spine_paths()))
  spine_file: HTMLFile | None = None
  translated_texts: list[str] = []
  translated_count: int = 0

  for translated_text in _translate(
    llm=llm,
    gen_fragments_iter=lambda: _gen_fragments(context),
    cache_path=working_path / "cache",
    max_chunk_tokens_count=4096,
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

    if did_touch_end:
      break

    translated_texts[translated_count] = translated_text
    translated_count += 1

  if spine_file and translated_count > 0:
    spine_file.write_texts(translated_texts)

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