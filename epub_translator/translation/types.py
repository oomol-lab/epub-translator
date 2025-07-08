from enum import Enum
from dataclasses import dataclass
from resource_segmentation import Incision


@dataclass
class Fragment:
  text: str
  start_incision: Incision
  end_incision: Incision

class Language(Enum):
  SIMPLIFIED_CHINESE = "zh-Hans"
  TRADITIONAL_CHINESE = "zh-Hant"
  ENGLISH = "en"
  FRENCH = "fr"
  GERMAN = "de"
  SPANISH = "es"
  RUSSIAN = "ru"
  ITALIAN = "it"
  PORTUGUESE = "pt"
  JAPANESE = "ja"
  KOREAN = "ko"

def language_chinese_name(language: Language) -> str:
  if language == Language.SIMPLIFIED_CHINESE:
    return "简体中文"
  elif language == Language.TRADITIONAL_CHINESE:
    return "繁体中文"
  elif language == Language.ENGLISH:
    return "英语"
  elif language == Language.FRENCH:
    return "法语"
  elif language == Language.GERMAN:
    return "德语"
  elif language == Language.SPANISH:
    return "西班牙语"
  elif language == Language.RUSSIAN:
    return "俄语"
  elif language == Language.ITALIAN:
    return "意大利语"
  elif language == Language.PORTUGUESE:
    return "葡萄牙语"
  elif language == Language.JAPANESE:
    return "日语"
  elif language == Language.KOREAN:
    return "韩语"
  else:
    raise ValueError(f"Unknown language: {language}")