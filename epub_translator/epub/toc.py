from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element

from .zip import Zip


@dataclass
class Toc:
    """
    统一的 EPUB 目录项数据结构，兼容 EPUB 2.0 和 EPUB 3.0

    EPUB 2.0 对应关系:
        - title <-> <navLabel><text>
        - href <-> <content src> (不包含 # 后的部分)
        - fragment <-> <content src> (# 后的部分)
        - children <-> 嵌套的 <navPoint>
        - id <-> <navPoint id>

    EPUB 3.0 对应关系:
        - title <-> <a> 标签的文本内容
        - href <-> <a href> (不包含 # 后的部分)
        - fragment <-> <a href> (# 后的部分)
        - children <-> 嵌套的 <ol><li>
        - id <-> <li id> 或 <a id>
    """

    title: str
    href: str | None = None
    fragment: str | None = None
    id: str | None = None
    children: list["Toc"] = field(default_factory=list)

    @property
    def full_href(self) -> str | None:
        if self.href is None:
            return None
        if self.fragment:
            return f"{self.href}#{self.fragment}"
        return self.href


def read_toc(zip: Zip) -> list[Toc]:
    """
    从 EPUB 文件读取目录结构

    自动识别 EPUB 2 (NCX) 和 EPUB 3 (nav) 格式

    Args:
        zip: EPUB zip 文件对象

    Returns:
        顶层目录项列表
    """
    version = _detect_epub_version(zip)
    toc_path = _find_toc_path(zip, version)

    if toc_path is None:
        return []

    if version == 2:
        return _read_ncx_toc(zip, toc_path)
    else:
        return _read_nav_toc(zip, toc_path)


def write_toc(zip: Zip, toc: list[Toc]) -> None:
    """
    写回目录结构到 EPUB 文件

    自动识别 EPUB 2 (NCX) 和 EPUB 3 (nav) 格式，并保守地修改原始 XML

    Args:
        zip: EPUB zip 文件对象
        toc: 目录项列表
    """
    version = _detect_epub_version(zip)
    toc_path = _find_toc_path(zip, version)

    if toc_path is None:
        raise ValueError("Cannot find TOC file in EPUB")

    if version == 2:
        _write_ncx_toc(zip, toc_path, toc)
    else:
        _write_nav_toc(zip, toc_path, toc)


# ============================================================================
# 版本检测和路径查找
# ============================================================================


def _detect_epub_version(zip: Zip) -> int:
    """
    检测 EPUB 版本

    Args:
        zip: EPUB zip 文件对象

    Returns:
        2 表示 EPUB 2.x, 3 表示 EPUB 3.x
    """
    opf_path = _find_opf_path(zip)

    with zip.read(opf_path) as f:
        content = f.read()
        root = ET.fromstring(content)

        # 检查 package 元素的 version 属性
        version_str = root.get("version", "2.0")

        if version_str.startswith("3"):
            return 3
        else:
            return 2


def _find_opf_path(zip: Zip) -> Path:
    """
    从 container.xml 查找 OPF 文件路径

    Args:
        zip: EPUB zip 文件对象

    Returns:
        OPF 文件的路径
    """
    container_path = Path("META-INF/container.xml")

    with zip.read(container_path) as f:
        content = f.read()
        root = ET.fromstring(content)

        # 查找 rootfile 元素
        # 注意：container.xml 有命名空间
        ns = {"ns": "urn:oasis:names:tc:opendocument:xmlns:container"}
        rootfile = root.find(".//ns:rootfile", ns)

        if rootfile is None:
            # 尝试不带命名空间
            rootfile = root.find(".//rootfile")

        if rootfile is None:
            raise ValueError("Cannot find rootfile in container.xml")

        full_path = rootfile.get("full-path")
        if full_path is None:
            raise ValueError("rootfile element has no full-path attribute")

        return Path(full_path)


def _find_toc_path(zip: Zip, version: int) -> Path | None:
    """
    查找目录文件路径

    Args:
        zip: EPUB zip 文件对象
        version: EPUB 版本 (2 或 3)

    Returns:
        目录文件路径，如果未找到则返回 None
    """
    opf_path = _find_opf_path(zip)
    opf_dir = opf_path.parent

    with zip.read(opf_path) as f:
        content = f.read()
        root = ET.fromstring(content)

        # 移除命名空间前缀以简化 XPath
        _strip_namespace(root)

        manifest = root.find(".//manifest")
        if manifest is None:
            return None

        if version == 2:
            # EPUB 2: 查找 NCX 文件 (media-type="application/x-dtbncx+xml")
            for item in manifest.findall("item"):
                media_type = item.get("media-type")
                if media_type == "application/x-dtbncx+xml":
                    href = item.get("href")
                    if href:
                        return opf_dir / href
        else:
            # EPUB 3: 查找 nav 文件 (properties="nav")
            for item in manifest.findall("item"):
                properties = item.get("properties", "")
                if "nav" in properties.split():
                    href = item.get("href")
                    if href:
                        return opf_dir / href

        return None


def _strip_namespace(elem: Element) -> None:
    """
    递归移除元素的命名空间前缀（仅用于读取，不修改原始文件）

    Args:
        elem: XML 元素
    """
    if elem.tag.startswith("{"):
        elem.tag = elem.tag.split("}", 1)[1]

    for child in elem:
        _strip_namespace(child)


# ============================================================================
# EPUB 2 NCX 格式处理
# ============================================================================


def _read_ncx_toc(zip: Zip, ncx_path: Path) -> list[Toc]:
    """
    读取 EPUB 2 的 NCX 格式目录

    Args:
        zip: EPUB zip 文件对象
        ncx_path: NCX 文件路径

    Returns:
        顶层目录项列表
    """
    with zip.read(ncx_path) as f:
        content = f.read()
        root = ET.fromstring(content)

        # 移除命名空间
        _strip_namespace(root)

        # 查找 navMap
        nav_map = root.find(".//navMap")
        if nav_map is None:
            return []

        # 解析顶层 navPoint
        result = []
        for nav_point in nav_map.findall("navPoint"):
            toc_item = _parse_nav_point(nav_point)
            if toc_item:
                result.append(toc_item)

        return result


def _parse_nav_point(nav_point: Element) -> Toc | None:
    """
    解析 NCX 的 navPoint 元素

    Args:
        nav_point: navPoint XML 元素

    Returns:
        Toc 对象，如果解析失败则返回 None
    """
    # 获取 id
    nav_id = nav_point.get("id")

    # 获取 title
    nav_label = nav_point.find("navLabel")
    if nav_label is None:
        return None

    text_elem = nav_label.find("text")
    if text_elem is None or text_elem.text is None:
        return None

    title = text_elem.text.strip()

    # 获取 href
    content_elem = nav_point.find("content")
    href = None
    fragment = None

    if content_elem is not None:
        src = content_elem.get("src")
        if src:
            href, fragment = _split_href(src)

    # 递归解析子节点
    children = []
    for child_nav_point in nav_point.findall("navPoint"):
        child_toc = _parse_nav_point(child_nav_point)
        if child_toc:
            children.append(child_toc)

    return Toc(
        title=title,
        href=href,
        fragment=fragment,
        id=nav_id,
        children=children,
    )


def _write_ncx_toc(zip: Zip, ncx_path: Path, toc_list: list[Toc]) -> None:
    """
    写回 EPUB 2 的 NCX 格式目录（保守修改）

    Args:
        zip: EPUB zip 文件对象
        ncx_path: NCX 文件路径
        toc_list: 目录项列表
    """
    with zip.read(ncx_path) as f:
        content = f.read()
        root = ET.fromstring(content)

        # 保存原始命名空间
        ns = _extract_namespace(root.tag)

        # 查找 navMap
        nav_map = root.find(f".//{{{ns}}}navMap" if ns else ".//navMap")
        if nav_map is None:
            raise ValueError("Cannot find navMap in NCX file")

        # 保守修改：匹配并更新现有节点，添加新节点，删除多余节点
        _update_nav_points(nav_map, toc_list, ns)

        # 写回文件
        tree = ET.ElementTree(root)
        with zip.replace(ncx_path) as out:
            tree.write(out, encoding="utf-8", xml_declaration=True)


def _update_nav_points(parent: Element, toc_list: list[Toc], ns: str | None) -> None:
    """
    保守地更新 navPoint 节点

    Args:
        parent: 父元素（navMap 或 navPoint）
        toc_list: 目录项列表
        ns: 命名空间
    """
    tag_prefix = f"{{{ns}}}" if ns else ""
    nav_point_tag = f"{tag_prefix}navPoint"

    # 获取现有的 navPoint 节点
    existing_nav_points = [elem for elem in parent if elem.tag == nav_point_tag]

    # 使用混合策略匹配
    matched_pairs = _match_toc_with_elements(toc_list, existing_nav_points)

    # 清空父节点中的所有 navPoint（但保留其他元素）
    for nav_point in existing_nav_points:
        parent.remove(nav_point)

    # 按照 toc_list 的顺序重新添加
    play_order = 1
    for toc, existing_elem in matched_pairs:
        if existing_elem is not None:
            # 更新现有节点
            nav_point = existing_elem
            _update_nav_point_content(nav_point, toc, ns)
        else:
            # 创建新节点
            nav_point = _create_nav_point(toc, ns, play_order)
            play_order += 1

        parent.append(nav_point)

        # 递归处理子节点
        _update_nav_points(nav_point, toc.children, ns)


def _update_nav_point_content(nav_point: Element, toc: Toc, ns: str | None) -> None:
    """
    更新 navPoint 的内容（保留结构）

    Args:
        nav_point: navPoint 元素
        toc: Toc 对象
        ns: 命名空间
    """
    tag_prefix = f"{{{ns}}}" if ns else ""

    # 更新 id
    if toc.id:
        nav_point.set("id", toc.id)

    # 更新 navLabel
    nav_label = nav_point.find(f"{tag_prefix}navLabel")
    if nav_label is not None:
        text_elem = nav_label.find(f"{tag_prefix}text")
        if text_elem is not None:
            text_elem.text = toc.title

    # 更新 content
    content_elem = nav_point.find(f"{tag_prefix}content")
    if content_elem is not None and toc.href is not None:
        full_href = toc.full_href
        if full_href:
            content_elem.set("src", full_href)


def _create_nav_point(toc: Toc, ns: str | None, play_order: int) -> Element:
    """
    创建新的 navPoint 元素

    Args:
        toc: Toc 对象
        ns: 命名空间
        play_order: 播放顺序

    Returns:
        新创建的 navPoint 元素
    """
    tag_prefix = f"{{{ns}}}" if ns else ""

    nav_point = Element(f"{tag_prefix}navPoint")
    if toc.id:
        nav_point.set("id", toc.id)
    else:
        # 生成一个 id
        nav_point.set("id", f"navPoint-{play_order}")
    nav_point.set("playOrder", str(play_order))

    # 创建 navLabel
    nav_label = Element(f"{tag_prefix}navLabel")
    text_elem = Element(f"{tag_prefix}text")
    text_elem.text = toc.title
    nav_label.append(text_elem)
    nav_point.append(nav_label)

    # 创建 content
    if toc.href is not None:
        content_elem = Element(f"{tag_prefix}content")
        full_href = toc.full_href
        if full_href:
            content_elem.set("src", full_href)
        nav_point.append(content_elem)

    return nav_point


# ============================================================================
# EPUB 3 nav 格式处理
# ============================================================================


def _read_nav_toc(zip: Zip, nav_path: Path) -> list[Toc]:
    """
    读取 EPUB 3 的 nav 格式目录

    Args:
        zip: EPUB zip 文件对象
        nav_path: nav 文件路径

    Returns:
        顶层目录项列表
    """
    with zip.read(nav_path) as f:
        content = f.read()
        root = ET.fromstring(content)

        # 移除命名空间
        _strip_namespace(root)

        # 查找 nav 元素（type="toc"）
        nav_elem = None
        for nav in root.findall(".//nav"):
            epub_type = nav.get("{http://www.idpf.org/2007/ops}type") or nav.get("type")
            if epub_type == "toc":
                nav_elem = nav
                break

        if nav_elem is None:
            return []

        # 查找 ol
        ol = nav_elem.find(".//ol")
        if ol is None:
            return []

        # 解析顶层 li
        result = []
        for li in ol.findall("li"):
            toc_item = _parse_nav_li(li)
            if toc_item:
                result.append(toc_item)

        return result


def _parse_nav_li(li: Element) -> Toc | None:
    """
    解析 nav 的 li 元素

    Args:
        li: li XML 元素

    Returns:
        Toc 对象，如果解析失败则返回 None
    """
    # 获取 id
    li_id = li.get("id")

    # 获取 a 元素
    a = li.find("a")
    if a is None:
        # 可能是纯分组节点，查找 span
        span = li.find("span")
        if span is not None and span.text:
            title = span.text.strip()
            href = None
            fragment = None
            a_id = None
        else:
            return None
    else:
        # 从 a 元素获取信息
        if a.text is None:
            return None
        title = a.text.strip()

        a_id = a.get("id")
        href_attr = a.get("href")

        if href_attr:
            href, fragment = _split_href(href_attr)
        else:
            href = None
            fragment = None

    # id 优先使用 li 的 id，如果没有则使用 a 的 id
    final_id = li_id if li_id else (a_id if "a_id" in locals() else None)

    # 递归解析子节点
    children = []
    child_ol = li.find("ol")
    if child_ol is not None:
        for child_li in child_ol.findall("li"):
            child_toc = _parse_nav_li(child_li)
            if child_toc:
                children.append(child_toc)

    return Toc(
        title=title,
        href=href,
        fragment=fragment,
        id=final_id,
        children=children,
    )


def _write_nav_toc(zip: Zip, nav_path: Path, toc_list: list[Toc]) -> None:
    """
    写回 EPUB 3 的 nav 格式目录（保守修改）

    Args:
        zip: EPUB zip 文件对象
        nav_path: nav 文件路径
        toc_list: 目录项列表
    """
    with zip.read(nav_path) as f:
        content = f.read()
        root = ET.fromstring(content)

        # 保存原始命名空间
        ns = _extract_namespace(root.tag)

        # 查找 nav 元素（type="toc"）
        nav_elem = None
        for nav in root.findall(f".//{{{ns}}}nav" if ns else ".//nav"):
            # 检查多个可能的 type 属性位置
            epub_type = nav.get("{http://www.idpf.org/2007/ops}type") or nav.get("type") or nav.get(f"{{{ns}}}type")
            if epub_type == "toc":
                nav_elem = nav
                break

        if nav_elem is None:
            raise ValueError("Cannot find nav element with type='toc'")

        # 查找 ol
        ol = nav_elem.find(f".//{{{ns}}}ol" if ns else ".//ol")
        if ol is None:
            raise ValueError("Cannot find ol in nav element")

        # 保守修改：匹配并更新现有节点
        _update_nav_lis(ol, toc_list, ns)

        # 写回文件
        tree = ET.ElementTree(root)
        with zip.replace(nav_path) as out:
            tree.write(out, encoding="utf-8", xml_declaration=True)


def _update_nav_lis(ol: Element, toc_list: list[Toc], ns: str | None) -> None:
    """
    保守地更新 li 节点

    Args:
        ol: ol 元素
        toc_list: 目录项列表
        ns: 命名空间
    """
    tag_prefix = f"{{{ns}}}" if ns else ""
    li_tag = f"{tag_prefix}li"

    # 获取现有的 li 节点
    existing_lis = [elem for elem in ol if elem.tag == li_tag]

    # 使用混合策略匹配
    matched_pairs = _match_toc_with_elements(toc_list, existing_lis)

    # 清空 ol 中的所有 li
    for li in existing_lis:
        ol.remove(li)

    # 按照 toc_list 的顺序重新添加
    for toc, existing_elem in matched_pairs:
        if existing_elem is not None:
            # 更新现有节点
            li = existing_elem
            _update_nav_li_content(li, toc, ns)
        else:
            # 创建新节点
            li = _create_nav_li(toc, ns)

        ol.append(li)

        # 递归处理子节点
        if toc.children:
            child_ol = li.find(f"{tag_prefix}ol")
            if child_ol is None:
                child_ol = Element(f"{tag_prefix}ol")
                li.append(child_ol)
            _update_nav_lis(child_ol, toc.children, ns)


def _update_nav_li_content(li: Element, toc: Toc, ns: str | None) -> None:
    """
    更新 li 的内容（保留结构）

    Args:
        li: li 元素
        toc: Toc 对象
        ns: 命名空间
    """
    tag_prefix = f"{{{ns}}}" if ns else ""

    # 更新 id
    if toc.id:
        li.set("id", toc.id)

    # 更新 a 或 span
    a = li.find(f"{tag_prefix}a")
    span = li.find(f"{tag_prefix}span")

    if toc.href is not None:
        # 有链接，使用 a
        if a is not None:
            a.text = toc.title
            full_href = toc.full_href
            if full_href:
                a.set("href", full_href)
        elif span is not None:
            # 替换 span 为 a
            li.remove(span)
            a = Element(f"{tag_prefix}a")
            a.text = toc.title
            full_href = toc.full_href
            if full_href:
                a.set("href", full_href)
            li.insert(0, a)
    else:
        # 无链接，使用 span
        if span is not None:
            span.text = toc.title
        elif a is not None:
            # 替换 a 为 span
            li.remove(a)
            span = Element(f"{tag_prefix}span")
            span.text = toc.title
            li.insert(0, span)


def _create_nav_li(toc: Toc, ns: str | None) -> Element:
    """
    创建新的 li 元素

    Args:
        toc: Toc 对象
        ns: 命名空间

    Returns:
        新创建的 li 元素
    """
    tag_prefix = f"{{{ns}}}" if ns else ""

    li = Element(f"{tag_prefix}li")
    if toc.id:
        li.set("id", toc.id)

    if toc.href is not None:
        # 创建 a
        a = Element(f"{tag_prefix}a")
        a.text = toc.title
        full_href = toc.full_href
        if full_href:
            a.set("href", full_href)
        li.append(a)
    else:
        # 创建 span
        span = Element(f"{tag_prefix}span")
        span.text = toc.title
        li.append(span)

    return li


# ============================================================================
# 工具函数
# ============================================================================


def _split_href(href: str) -> tuple[str | None, str | None]:
    """
    分割 href 为文件路径和锚点

    Args:
        href: 完整的 href 字符串

    Returns:
        (文件路径, 锚点) 元组，如果没有锚点则第二项为 None
    """
    if "#" in href:
        parts = href.split("#", 1)
        return parts[0] if parts[0] else None, parts[1] if parts[1] else None
    else:
        return href, None


def _extract_namespace(tag: str) -> str | None:
    """
    从标签中提取命名空间

    Args:
        tag: 带命名空间的标签名，如 "{http://www.daisy.org/z3986/2005/ncx/}ncx"

    Returns:
        命名空间 URI，如果没有则返回 None
    """
    if tag.startswith("{"):
        return tag[1 : tag.index("}")]
    return None


def _match_toc_with_elements(toc_list: list[Toc], elements: list[Element]) -> list[tuple[Toc, Element | None]]:
    """
    使用混合策略匹配 Toc 对象和 XML 元素

    策略优先级：
    1. 通过 id 匹配
    2. 通过 href 匹配
    3. 通过位置匹配

    Args:
        toc_list: Toc 对象列表
        elements: XML 元素列表

    Returns:
        配对列表，每个元素是 (Toc, Element | None)
    """
    result = []
    used_elements = set()

    # 第一遍：通过 id 匹配
    for toc in toc_list:
        matched = None
        if toc.id:
            for i, elem in enumerate(elements):
                if i in used_elements:
                    continue
                elem_id = elem.get("id")
                if elem_id == toc.id:
                    matched = elem
                    used_elements.add(i)
                    break
        result.append((toc, matched))

    # 第二遍：通过 href 匹配（仅针对未匹配的）
    for i, (toc, matched) in enumerate(result):
        if matched is None and toc.href:
            for j, elem in enumerate(elements):
                if j in used_elements:
                    continue
                elem_href = _extract_href_from_element(elem)
                if elem_href and elem_href == toc.full_href:
                    result[i] = (toc, elem)
                    used_elements.add(j)
                    break

    # 第三遍：通过位置匹配（仅针对仍未匹配的）
    unmatched_indices = [i for i, (_, matched) in enumerate(result) if matched is None]
    available_elements = [elem for j, elem in enumerate(elements) if j not in used_elements]

    for i, elem in zip(unmatched_indices, available_elements):
        toc, _ = result[i]
        result[i] = (toc, elem)

    return result


def _extract_href_from_element(elem: Element) -> str | None:
    """
    从 XML 元素中提取 href

    Args:
        elem: XML 元素（可能是 navPoint 或 li）

    Returns:
        href 字符串，如果未找到则返回 None
    """
    # NCX 格式：查找 content/@src
    content = elem.find(".//content")
    if content is not None:
        return content.get("src")

    # nav 格式：查找 a/@href
    a = elem.find(".//a")
    if a is not None:
        return a.get("href")

    return None
