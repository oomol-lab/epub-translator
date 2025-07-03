import zipfile

from typing import Generator, Callable
from pathlib import Path
from lxml.etree import parse
from .epub import EpubContent, HTMLFile


class ZipContext:
  def __init__(self, epub_path: Path, temp_dir: Path):
    with zipfile.ZipFile(epub_path, "r") as zip_ref:
      for member in zip_ref.namelist():
        target_path = temp_dir / member
        if member.endswith("/"):
          target_path.mkdir(parents=True, exist_ok=True)
        else:
          target_path.parent.mkdir(parents=True, exist_ok=True)
          with zip_ref.open(member) as source:
            with open(target_path, "wb") as file:
              file.write(source.read())

    self._temp_dir: Path = temp_dir
    self._epub_content: EpubContent = EpubContent(temp_dir)

  def archive(self, saved_path: Path):
    with zipfile.ZipFile(saved_path, "w") as zip_file:
      for file_path in self._temp_dir.rglob("*"):
        if not file_path.is_file():
          continue
        relative_path = file_path.relative_to(self._temp_dir)
        zip_file.write(
          filename=file_path,
          arcname=str(relative_path),
        )

  def search_spine_paths(self) -> Generator[Path, None, None]:
    for spine in self._epub_content.spines:
      if spine.media_type == "application/xhtml+xml":
        yield Path(spine.path)

  def read_spine_file(self, spine_path: Path) -> HTMLFile:
    with open(spine_path, "r", encoding="utf-8") as file:
      return HTMLFile(file.read())

  def write_spine_file(self, spine_path: Path, file: HTMLFile):
    with open(spine_path, "w", encoding="utf-8") as f:
      f.write(file.file_content)

  def replace_ncx(self, replace: Callable[[list[str]], list[str]]):
    ncx_path = self._epub_content.ncx_path
    if ncx_path is None:
      return

    tree = parse(ncx_path)
    root = tree.getroot()
    namespaces={ "ns": root.nsmap.get(None) }
    text_doms = []
    text_list = []

    for text_dom in root.xpath("//ns:text", namespaces=namespaces):
      text_doms.append(text_dom)
      text_list.append(text_dom.text or "")

    for index, text in enumerate(replace(text_list)):
      text_dom = text_doms[index]
      text_dom.text = self._link_translated(text_dom.text, text)

    tree.write(ncx_path, pretty_print=True)

  def _link_translated(self, origin: str, target: str) -> str:
    if origin == target:
      return origin
    else:
      return f"{origin} - {target}"