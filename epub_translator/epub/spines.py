from collections.abc import Generator
from pathlib import Path
from xml.etree import ElementTree as ET

from .common import find_opf_path, strip_namespace
from .zip import Zip


def search_spine_paths(zip: Zip) -> Generator[Path, None, None]:
    """
    遍历 EPUB 的 spine，返回所有可读内容文件的路径。

    Spine 定义了 EPUB 中所有应该被阅读的文档及其顺序。
    这是获取完整内容的正确方式（而非依赖 TOC）。

    支持 EPUB 2 和 EPUB 3。
    """
    opf_path = find_opf_path(zip)
    opf_dir = opf_path.parent

    with zip.read(opf_path) as f:
        content = f.read()
        root = ET.fromstring(content)
        strip_namespace(root)

        # 解析 manifest，建立 id -> (href, media-type) 的映射
        manifest = root.find(".//manifest")
        if manifest is None:
            return

        manifest_items = {}
        for item in manifest.findall("item"):
            item_id = item.get("id")
            item_href = item.get("href")
            media_type = item.get("media-type", "")
            if item_id and item_href:
                manifest_items[item_id] = (item_href, media_type)

        # 解析 spine，按顺序返回文档路径
        spine = root.find(".//spine")
        if spine is None:
            return

        for itemref in spine.findall("itemref"):
            idref = itemref.get("idref")
            if not idref:
                continue

            # 检查是否标记为 linear="no"（可选内容）
            # 默认为 "yes"，我们也包含 linear="no" 的内容，因为它们仍是可读的
            # linear = itemref.get("linear", "yes")

            if idref in manifest_items:
                href, media_type = manifest_items[idref]

                # 只返回 XHTML/HTML 文档
                if media_type in ("application/xhtml+xml", "text/html"):
                    yield opf_dir / href
