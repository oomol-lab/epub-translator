import json
from pathlib import Path


def read_format_json() -> dict:
    path = Path(__file__).parent / ".." / "format.json"
    path = path.resolve()
    with open(path, encoding="utf-8") as file:
        return json.load(file)
