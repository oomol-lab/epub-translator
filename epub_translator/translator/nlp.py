import re
import spacy
import langid
import threading

from spacy.language import Language

_lan2model: dict = {
  "en": "en_core_web_sm",
  "zh": "zh_core_web_sm",
  "fr": "fr_core_news_sm",
  "ru": "ru_core_news_sm",
  "de": "de_core_news_sm",
}

class NLP:
  def __init__(self) -> None:
    self._lock: threading.Lock = threading.Lock()
    self._nlp_dict: dict[str, Language] = {}

  def split_into_sents(self, text: str) -> list[str]:
    lan, _ = langid.classify(text)
    with self._lock:
      nlp = self._nlp_dict.get(lan, None)
      if nlp is None:
        model_id = _lan2model.get(lan, None)
        if model_id is None:
          return self._split_into_sents(text)
        nlp = spacy.load(model_id)
        self._nlp_dict[lan] = nlp

    return [s.text for s in nlp(text).sents]

  def _split_into_sents(self, text: str) -> list[str]:
    cells: list[str] = re.split(r"(\.|!|\?|;|。|！|？|；)", text)
    return [cells[i] + cells[i+1] for i in range(0, len(cells)-1, 2)]