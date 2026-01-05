from dataclasses import dataclass
from xml.etree.ElementTree import Element

from ..xml import ID_KEY


@dataclass
class FoundInvalidIDError(Exception):
    invalid_id: str | None


def validate_id_in_element(element: Element) -> int | FoundInvalidIDError:
    id_str = element.get(ID_KEY, None)
    if id_str is None:
        return FoundInvalidIDError(invalid_id=None)
    try:
        return int(id_str)
    except ValueError:
        return FoundInvalidIDError(invalid_id=id_str)
