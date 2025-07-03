from dataclasses import dataclass
from resource_segmentation import Incision


@dataclass
class Fragment:
  text: str
  start_incision: Incision
  end_incision: Incision