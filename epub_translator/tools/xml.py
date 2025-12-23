from collections.abc import Generator
from xml.etree.ElementTree import Element


def indent(elem: Element, level: int = 0) -> Element:
    indent_str = "  " * level
    next_indent_str = "  " * (level + 1)
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = "\n" + next_indent_str
        for i, child in enumerate(elem):
            indent(child, level + 1)
            if not child.tail or not child.tail.strip():
                if i == len(elem) - 1:
                    child.tail = "\n" + indent_str
                else:
                    child.tail = "\n" + next_indent_str
    return elem


def iter_with_stack(element: Element) -> Generator[tuple[list[Element], Element], None, None]:
    """先序遍历：yield parent_path, element"""
    stack: list[list[Element]] = [[element]]
    while stack:
        current_path = stack.pop()
        current = current_path[-1]
        yield current_path[:-1], current

        if len(current) == 0:
            continue

        for child in reversed(list(current)):
            child_path = list(current_path)
            child_path.append(child)
            stack.append(child_path)
