import os
import re

from lxml.etree import parse, Element, QName
from html import escape


# TODO replace with XML
class Spine:
  def __init__(self, folder_path, base_path, item):
    self._folder_path = folder_path
    self._base_path = base_path
    self.href = item.get("href")
    self.media_type = item.get("media-type")

  @property
  def path(self):
    path = os.path.join(self._base_path, self.href)
    path = os.path.abspath(path)

    if os.path.exists(path):
      return path

    path = os.path.join(self._folder_path, self.href)
    path = os.path.abspath(path)
    return path

class EpubContent:
  def __init__(self, path: str):
    self.folder_path = path
    self._content_path = self._find_content_path(path)
    self._tree = parse(self._content_path)
    self._namespaces = { "ns": self._tree.getroot().nsmap.get(None) }
    self._spine = self._tree.xpath("//ns:spine", namespaces=self._namespaces)[0]
    self._metadata = self._tree.xpath("//ns:metadata", namespaces=self._namespaces)[0]
    self._manifest = self._tree.xpath("//ns:manifest", namespaces=self._namespaces)[0]

  def save(self):
    self._tree.write(self._content_path, pretty_print=True)

  def _find_content_path(self, path: str) -> str:
    root = parse(os.path.join(path, "META-INF", "container.xml")).getroot()
    rootfile = root.xpath(
      "//ns:container/ns:rootfiles/ns:rootfile",
      namespaces={ "ns": root.nsmap.get(None) },
    )[0]
    full_path = rootfile.attrib["full-path"]
    joined_path = os.path.join(path, full_path)

    return os.path.abspath(joined_path)

  @property
  def ncx_path(self):
    ncx_dom = self._manifest.find(".//*[@id=\"ncx\"]")
    if ncx_dom is not None:
      href_path = ncx_dom.get("href")
      base_path = os.path.dirname(self._content_path)
      path = os.path.join(base_path, href_path)
      path = os.path.abspath(path)

      if os.path.exists(path):
        return path

      path = os.path.join(self.folder_path, path)
      path = os.path.abspath(path)
      return path

  @property
  def spines(self):
    idref_dict = {}
    index = 0

    for child in self._spine.iterchildren():
      id = child.get("idref")
      idref_dict[id] = index
      index += 1

    items = [None for _ in range(index)]
    spines = []

    for child in self._manifest.iterchildren():
      id = child.get("id")
      if id in idref_dict:
        index = idref_dict[id]
        items[index] = child

    base_path = os.path.dirname(self._content_path)

    for item in items:
      if item is not None:
        spines.append(Spine(
          folder_path=self.folder_path,
          base_path=base_path,
          item=item,
        ))

    return spines

  @property
  def title(self):
    title_dom = self._get_title()
    if title_dom is None:
      return None
    return title_dom.text

  @title.setter
  def title(self, title: str):
    title_dom = self._get_title()
    if title_dom is not None:
      title_dom.text = _escape_ascii(title)

  def _get_title(self):
    titles = self._metadata.xpath(
      "./dc:title",
      namespaces={
        "dc": self._metadata.nsmap.get("dc"),
      },
    )
    if len(titles) == 0:
      return None
    return titles[0]

  @property
  def authors(self) -> list[str]:
    return list(map(lambda x: x.text, self._get_creators()))

  @authors.setter
  def authors(self, authors):
    creator_doms = self._get_creators()
    if len(creator_doms) == 0:
      return
    parent_dom = creator_doms[0].getparent()
    index_at_parent = parent_dom.index(creator_doms[0])
    ns={
      "dc": self._metadata.nsmap.get("dc"),
      "opf": self._metadata.nsmap.get("opf"),
    }
    for author in reversed(authors):
      creator_dom = Element(QName(ns["dc"], "creator"))
      creator_dom.set(QName(ns["opf"], "file-as"), author)
      creator_dom.set(QName(ns["opf"], "role"), "aut")
      creator_dom.text = _escape_ascii(author)
      parent_dom.insert(index_at_parent, creator_dom)

    for creator_dom in creator_doms:
      parent_dom.remove(creator_dom)

  def _get_creators(self):
    return self._metadata.xpath(
      "./dc:creator",
      namespaces={
        "dc": self._metadata.nsmap.get("dc"),
      },
    )

def _escape_ascii(content: str) -> str:
  content = escape(content)
  content = re.sub(
    r"\\u([\da-fA-F]{4})",
    lambda x: chr(int(x.group(1), 16)), content,
  )
  return content