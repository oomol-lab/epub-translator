from enum import Enum
from dataclasses import dataclass
from resource_segmentation import Incision


@dataclass
class Fragment:
  text: str
  start_incision: Incision
  end_incision: Incision

class Language(Enum):
  SIMPLIFIED_CHINESE = "简体中文"
  TRADITIONAL_CHINESE = "繁体中文"
  ENGLISH = "英语"
  FRENCH = "法语"
  GERMAN = "德语"
  SPANISH = "西班牙语"
  RUSSIAN = "俄语"
  ITALIAN = "意大利语"
  PORTUGUESE = "葡萄牙语"
  JAPANESE = "日语"
  KOREAN = "韩语"