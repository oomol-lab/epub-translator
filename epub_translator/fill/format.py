import re
from xml.etree.ElementTree import Element, ParseError, fromstring


def format(template_ele: Element, validated_text: str, errors_limit: int) -> Element:
    context = _ValidationContext()
    validated_ele = _extract_xml_element(validated_text)
    context.validate(raw_ele=template_ele, validated_ele=validated_ele)
    error_message = context.errors(limit=errors_limit)
    if error_message:
        raise ValidationError(message=error_message)
    return validated_ele


class ValidationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def _extract_xml_element(text: str) -> Element:
    xml_start_pattern = r"<xml\s[^>]*>"
    xml_starts = list(re.finditer(xml_start_pattern, text))

    if len(xml_starts) == 0:
        raise ValidationError(
            "No <xml> opening tag found. Please ensure the response contains a valid <xml> ... </xml> tag."
        )
    if len(xml_starts) > 1:
        raise ValidationError(
            "Multiple <xml> opening tags found. Please ensure the response contains only one <xml> tag."
        )
    xml_start = xml_starts[0]
    start_pos = xml_start.start()
    xml_end_pattern = r"</xml>"
    xml_end = re.search(xml_end_pattern, text[start_pos:])

    if xml_end is None:
        raise ValidationError(
            "No </xml> closing tag found. Please ensure the XML structure is properly closed with </xml>."
        )
    end_pos = start_pos + xml_end.end()
    xml_content = text[start_pos:end_pos]
    try:
        element = fromstring(xml_content)
        return element
    except ParseError as error:
        raise ValidationError(
            f"Failed to parse XML: {str(error)}. Please check the XML syntax and ensure it is well-formed."
        ) from error


_ID_KEY = "id"


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

        content.insert(0, f"Found {total_errors} error(s) in your response XML structure.\n")
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

        messages: list[str] = []
        lost_ids.sort()
        extra_ids.sort()

        if lost_ids:
            tags = [self._str_tag(raw_id_map[id]) for id in lost_ids]
            messages.append(f"lost sub-tags {' '.join(tags)}")

        if extra_ids:
            tags = [self._str_tag(validated_id_map[id]) for id in extra_ids]
            messages.append(f"extra sub-tags {' '.join(tags)}")

        if messages:
            self._add_error(
                ids_path=ids_path,
                message="find " + " and ".join(messages),
            )

    def _validate_id_ele(self, ids_path: list[int], id: int, raw_ele: Element, validated_ele: Element):
        if raw_ele.tag == validated_ele.tag:
            self._tag_text_dict[id] = self._str_tag(raw_ele)
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
        ele_id = ele.get(_ID_KEY, "")
        id = int(ele_id)
        if id < 0:
            raise ValidationError(f'Invalid id "{ele_id}" found. IDs must be non-negative integers.')
        if ele_id is not None:
            id_map[id] = ele
        return id_map

    def _str_tag(self, ele: Element) -> str:
        ele_id = ele.get(_ID_KEY)
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
