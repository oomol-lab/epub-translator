from xml.etree.ElementTree import Element


def element_fingerprint(element: Element) -> str:
    attrs = sorted(f"{key}={value}" for key, value in element.attrib.items())
    return f"<{element.tag} {' '.join(attrs)}/>"


def unwrap_parents(element: Element) -> tuple[Element, list[Element]]:
    parents: list[Element] = []
    while True:
        if len(element) != 1:
            break
        child = element[0]
        if not element.text:
            break
        if not child.tail:
            break
        parents.append(element)
        element = child
        element.tail = None
    return element, parents


class IDGenerator:
    def __init__(self):
        self._previous_id: int = 0

    def next_id(self) -> int:
        self._previous_id += 1
        return self._previous_id
