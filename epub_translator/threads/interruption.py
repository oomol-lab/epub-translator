from threading import local, Event
from typing import cast


_INTERRUPTED_EVENT = local()

def assert_continue():
  if not hasattr(_INTERRUPTED_EVENT, "value"):
    return
  event = cast(Event, _INTERRUPTED_EVENT.value)
  if event.is_set():
    raise InterruptedException()

class InterruptedException(Exception):
  def __init__(self):
    super().__init__("Interrupt")

class InterruptionContext:
  def __init__(self, interrupted_event: Event) -> None:
    self._interrupted_event = interrupted_event

  def __enter__(self) -> None:
    if hasattr(_INTERRUPTED_EVENT, "value"):
      raise RuntimeError("InterruptionContext is already set")
    setattr(_INTERRUPTED_EVENT, "value", self._interrupted_event)

  def __exit__(self, exc_type, exc_value, traceback) -> None:
    if hasattr(_INTERRUPTED_EVENT, "value"):
      del _INTERRUPTED_EVENT.value

class Interruption:
  def __init__(self) -> None:
    self._interrupted_event: Event = Event()

  @property
  def interrupted(self) -> bool:
    return self._interrupted_event.is_set()

  def interrupt(self) -> None:
    self._interrupted_event.set()

  def assert_continue(self) -> None:
    if self._interrupted_event.is_set():
      raise InterruptedException()

  def context(self) -> InterruptionContext:
    return InterruptionContext(self._interrupted_event)