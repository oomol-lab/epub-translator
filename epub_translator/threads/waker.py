from dataclasses import dataclass
from threading import Event, Lock
from typing import TypeVar, Generic, Callable


P = TypeVar("P")

class WakerDidStop(Exception):
  def __init__(self):
    super().__init__("Waker has stopped")

@dataclass
class _Handshake(Generic[P]):
  push_event: Event | None
  receive_event: Event | None
  payload: P | None

# [thread safe]
# why not use Semaphore or Queue?
# - Queue cannot be canceled from the outside
# - Semaphore cannot be locked thread-safely, making it difficult to ensure that there are no problems with the state
class Waker(Generic[P]):
  def __init__(self):
    self._lock: Lock = Lock()
    self._did_stop: bool = False
    self._handshakes: list[_Handshake[P]] = []

  @property
  def did_stop(self) -> bool:
    return self._did_stop

  # to wake up all waiting threads and do nothing if there are no waiting threads
  def broadcast(self, payload: P) -> None:
    with self._lock:
      removed_indexes: set[int] = set()
      for i, handshake in enumerate(self._handshakes):
        if handshake.receive_event is not None:
          handshake.payload = payload
          handshake.receive_event.set()
          removed_indexes.add(i)

      if len(removed_indexes) > 0:
        self._handshakes = [
          h for i, h in enumerate(self._handshakes)
          if i not in removed_indexes
        ]

  def push(self, payload: P):
    wait_handshake: _Handshake[P] | None = None
    with self._lock:
      if self._did_stop:
        raise WakerDidStop()
      handshake = self._choose_handshake(
        select=lambda x: x.receive_event is not None,
      )
      if handshake is not None:
        handshake.payload = payload
        handshake.receive_event.set()
      else:
        wait_handshake = _Handshake(
          push_event=Event(),
          receive_event=None,
          payload=payload,
        )
        self._handshakes.append(wait_handshake)

    if wait_handshake is not None:
      wait_handshake.push_event.wait()

    with self._lock:
      if self._did_stop:
        raise WakerDidStop()

  def receive(self) -> P:
    handshake: _Handshake[P] | None
    wait_handshake: _Handshake[P] | None = None

    with self._lock:
      if self._did_stop:
        raise WakerDidStop()
      handshake = self._choose_handshake(
        select=lambda x: x.push_event is not None,
      )
      if handshake is None:
        handshake = _Handshake(
          push_event=None,
          receive_event=Event(),
          payload=None,
        )
        self._handshakes.append(handshake)
        wait_handshake = handshake

      elif handshake.push_event is not None:
        handshake.push_event.set()

    if wait_handshake is not None:
      wait_handshake.receive_event.wait()

    with self._lock:
      if self._did_stop:
        raise WakerDidStop()

    return handshake.payload

  def stop(self) -> None:
    with self._lock:
      if self._did_stop:
        return
      for handshake in self._handshakes:
        if handshake.push_event is not None:
          handshake.push_event.set()
        if handshake.receive_event is not None:
          handshake.receive_event.set()
      self._handshakes.clear()
      self._did_stop = True

  def _choose_handshake(self, select: Callable[[_Handshake], bool]) -> _Handshake[P] | None:
    for i in range(len(self._handshakes)):
      handshake = self._handshakes[i]
      if select(handshake):
        return self._handshakes.pop(i)
    return None
