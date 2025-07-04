from shutil import rmtree
from pathlib import Path
from typing import Iterator
from .utils import clean_spaces


class Store:
  def __init__(self, directory: Path):
    self._directory = directory

  def get(self, chunk_hash: bytes) -> list[str] | None:
    file_path = self._file_path(chunk_hash)
    if not file_path.exists() or not file_path.is_file():
      return None
    with file_path.open("r", encoding="utf-8") as file:
      return list(line for line in file if line.strip())

  def put(self, chunk_hash: bytes, lines_iter: Iterator[str]):
    file_path = self._file_path(chunk_hash)
    if file_path.exists():
      if file_path.is_file():
        file_path.unlink()
      else:
        rmtree(file_path)

    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as file:
      is_first_line = True
      for line in lines_iter:
        if is_first_line:
          is_first_line = False
        else:
          file.write("\n")
        file.write(clean_spaces(line))

  def _file_path(self, chunk_hash: bytes) -> Path:
    return self._directory / f"{chunk_hash.hex()}.chunk"