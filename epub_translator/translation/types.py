from enum import Enum, IntEnum
from dataclasses import dataclass


class Incision(IntEnum):
  MUST_BE = 3
  MOST_LIKELY = 2
  IMPOSSIBLE = 0
  UNCERTAIN = 1

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

_LANGUAGE_NAMES = {
  Language.SIMPLIFIED_CHINESE: "简体中文",
  Language.TRADITIONAL_CHINESE: "繁体中文",
  Language.ENGLISH: "英语",
  Language.FRENCH: "法语",
  Language.GERMAN: "德语",
  Language.SPANISH: "西班牙语",
  Language.RUSSIAN: "俄语",
  Language.ITALIAN: "意大利语",
  Language.PORTUGUESE: "葡萄牙语",
  Language.JAPANESE: "日语",
  Language.KOREAN: "韩语",
}

def language_chinese_name(language: Language) -> str:
  return _LANGUAGE_NAMES[language]