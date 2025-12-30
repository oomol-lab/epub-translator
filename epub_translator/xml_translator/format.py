from xml.etree.ElementTree import Element

from ..utils import normalize_whitespace
from ..xml import decode_friendly
from .const import ID_KEY


def format(template_ele: Element, validated_text: str, errors_limit: int) -> Element:
    context = _ValidationContext()
    validated_ele = _extract_xml_element(validated_text)
    context.validate(raw_ele=template_ele, validated_ele=validated_ele)
    error_message = context.errors(limit=errors_limit)
    if error_message:
        raise ValidationError(message=error_message, validated_ele=validated_ele)
    return validated_ele


class ValidationError(Exception):
    def __init__(self, message: str, validated_ele: Element | None = None) -> None:
        super().__init__(message)
        self.validated_ele = validated_ele


def _extract_xml_element(text: str) -> Element:
    first_xml_element: Element | None = None
    all_xml_elements: int = 0

    for xml_element in decode_friendly(text, tags="xml"):
        if first_xml_element is None:
            first_xml_element = xml_element
        all_xml_elements += 1

    if first_xml_element is None:
        raise ValidationError(
            "No complete <xml>...</xml> block found. Please ensure you have properly closed the XML with </xml> tag."
        )
    if all_xml_elements > 1:
        raise ValidationError(
            f"Found {all_xml_elements} <xml>...</xml> blocks. "
            "Please return only one XML block without any examples or explanations."
        )
    return first_xml_element


class _ValidationContext:
    def __init__(self) -> None:
        self._tag_text_dict: dict[int, str] = {}
        self._errors: dict[tuple[int, ...], list[str]] = {}

    def validate(self, raw_ele: Element, validated_ele: Element):
        self._validate_ele(ids_path=[], raw_ele=raw_ele, validated_ele=validated_ele)

    def errors(self, limit: int) -> str | None:
        if not self._errors:
            return

        keys = list(self._errors.keys())
        keys.sort(key=lambda k: (len(k), k))  # AI 矫正应该先浅后深
        keys = keys[:limit]
        max_len_key = max((len(key) for key in keys), default=0)

        for i in range(len(keys)):
            key = keys[i]
            if len(key) < max_len_key:
                key_list = list(key)
                while len(key_list) < max_len_key:
                    key_list.append(-1)
                keys[i] = tuple(key_list)

        content: list[str] = []
        total_errors = sum(len(messages) for messages in self._errors.values())
        remain_errors = total_errors

        for key in sorted(keys):  # 改成深度优先排序，看起来关联度更好
            raw_key = tuple(k for k in key if k >= 0)
            indent: str = f"{'  ' * len(raw_key)}"
            errors_list = self._errors[raw_key]
            parent_text: str

            if len(raw_key) > 0:
                parent_text = self._tag_text_dict[raw_key[-1]]
            else:
                parent_text = "the root tag"

            if len(errors_list) == 1:
                error = errors_list[0]
                content.append(f"{indent}- errors in {parent_text}: {error}.")
            else:
                content.append(f"{indent}- errors in {parent_text}:")
                for error in errors_list:
                    content.append(f"{indent}  - {error}.")
            remain_errors -= len(errors_list)

        content.insert(0, f"Found {total_errors} error(s) in your response XML structure.")
        if remain_errors > 0:
            content.append(f"\n... and {remain_errors} more error(s).")

        return "\n".join(content)

    def _validate_ele(self, ids_path: list[int], raw_ele: Element, validated_ele: Element):
        raw_id_map = self._build_id_map(raw_ele)
        validated_id_map = self._build_id_map(validated_ele)
        lost_ids: list[int] = []
        extra_ids: list[int] = []

        for id, sub_raw in raw_id_map.items():
            sub_validated = validated_id_map.get(id, None)
            if sub_validated is None:
                lost_ids.append(id)
            else:
                self._validate_id_ele(
                    id=id,
                    ids_path=ids_path,
                    raw_ele=sub_raw,
                    validated_ele=sub_validated,
                )

        for id in validated_id_map.keys():
            if id not in raw_id_map:
                extra_ids.append(id)

        if lost_ids or extra_ids:
            messages: list[str] = []
            lost_ids.sort()
            extra_ids.sort()

            if lost_ids:
                tags = [self._str_tag(raw_id_map[id]) for id in lost_ids]
                # Provide context from source XML
                context_info = self._get_source_context(raw_ele, lost_ids)
                messages.append(f"lost sub-tags {' '.join(tags)}")
                if context_info:
                    messages.append(f"Source structure was: {context_info}")

            if extra_ids:
                tags = [self._str_tag(validated_id_map[id]) for id in extra_ids]
                messages.append(f"extra sub-tags {' '.join(tags)}")

            if messages:
                self._add_error(
                    ids_path=ids_path,
                    message="find " + " and ".join(messages),
                )
        else:
            raw_element_empty = not self._has_text_content(raw_ele)
            validated_ele_empty = not self._has_text_content(validated_ele)

            if raw_element_empty and not validated_ele_empty:
                self._add_error(
                    ids_path=ids_path,
                    message="shouldn't have text content",
                )
            elif not raw_element_empty and validated_ele_empty:
                self._add_error(
                    ids_path=ids_path,
                    message="text content is missing",
                )

    def _validate_id_ele(self, ids_path: list[int], id: int, raw_ele: Element, validated_ele: Element):
        if raw_ele.tag == validated_ele.tag:
            self._tag_text_dict[id] = self._str_tag(raw_ele)
            raw_has_text = self._has_direct_text(raw_ele.text)
            validated_has_text = self._has_direct_text(validated_ele.text)

            if raw_has_text and not validated_has_text:
                self._add_error(
                    ids_path=ids_path + [id],
                    message="missing text content before child elements",
                )
            elif not raw_has_text and validated_has_text:
                self._add_error(
                    ids_path=ids_path + [id],
                    message="shouldn't have text content before child elements",
                )
            raw_has_tail = self._has_direct_text(raw_ele.tail)
            validated_has_tail = self._has_direct_text(validated_ele.tail)

            if raw_has_tail and not validated_has_tail:
                self._add_error(
                    ids_path=ids_path + [id],
                    message="missing text content after the element",
                )
            elif not raw_has_tail and validated_has_tail:
                self._add_error(
                    ids_path=ids_path + [id],
                    message="shouldn't have text content after the element",
                )

            self._validate_ele(
                ids_path=ids_path + [id],
                raw_ele=raw_ele,
                validated_ele=validated_ele,
            )
        else:
            self._add_error(
                ids_path=ids_path,
                message=f'got <{validated_ele.tag} id="{id}">',
            )

    def _add_error(self, ids_path: list[int], message: str):
        key = tuple(ids_path)
        if key not in self._errors:
            self._errors[key] = []
        self._errors[key].append(message)

    def _build_id_map(self, ele: Element):
        id_map: dict[int, Element] = {}
        for child_ele in ele:
            id_text = child_ele.get(ID_KEY, None)
            if id_text is not None:
                id = int(id_text)
                if id < 0:
                    raise ValueError(f"Invalid id {id} found. IDs must be non-negative integers.")
                if id_text is not None:
                    id_map[id] = child_ele
        return id_map

    def _has_text_content(self, ele: Element) -> bool:
        text = "".join(self._plain_text(ele))
        text = normalize_whitespace(text)
        text = text.strip()
        return len(text) > 0

    def _has_direct_text(self, text: str | None) -> bool:
        if text is None:
            return False
        normalized = normalize_whitespace(text).strip()
        return len(normalized) > 0

    def _plain_text(self, ele: Element):
        if ele.text:
            yield ele.text
        for child in ele:
            if child.get(ID_KEY, None) is not None:
                yield from self._plain_text(child)
            if child.tail:
                yield child.tail

    def _str_tag(self, ele: Element) -> str:
        ele_id = ele.get(ID_KEY)
        content: str
        if ele_id is not None:
            content = f'<{ele.tag} id="{ele_id}"'
        else:
            content = f"<{ele.tag}"
        if len(ele) > 0:
            content += f"> ... </{ele.tag}>"
        else:
            content += " />"
        return content

    def _get_source_context(self, parent: Element, lost_ids: list[int]) -> str:
        """Generate context showing where lost tags appeared in source XML."""
        if not lost_ids:
            return ""

        # Build a simple representation of the source structure
        children_with_ids = []
        for child in parent:
            child_id_str = child.get(ID_KEY)
            if child_id_str is not None:
                child_id = int(child_id_str)
                is_lost = child_id in lost_ids
                tag_str = f'<{child.tag} id="{child_id}">'

                # Show text before/inside/after
                parts = []
                if child.text and child.text.strip():
                    preview = child.text.strip()[:20]
                    if is_lost:
                        parts.append(f'[{preview}...]')
                    else:
                        parts.append(f'{preview}...')

                if is_lost:
                    children_with_ids.append(f'{tag_str}*MISSING*')
                else:
                    children_with_ids.append(tag_str)

        if children_with_ids:
            return f"[{' '.join(children_with_ids)}]"
        return ""
