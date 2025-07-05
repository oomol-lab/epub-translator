import traceback

from dataclasses import dataclass
from typing import Callable, TypeVar, Generic
from threading import Thread, Lock, Event

from .interruption import Interruption
from .waker import Waker, WakerDidStop


R = TypeVar("R")

@dataclass
class ExecuteSuccess(Generic[R]):
  result: R

@dataclass
class ExecuteFail:
  error: Exception

@dataclass
class NoMoreExecutions:
  pass

ExecuteResult = ExecuteSuccess[R] | ExecuteFail | NoMoreExecutions

class _ResultsQueue(Generic[R]):
  def __init__(self) -> None:
    self._lock: Lock = Lock()
    self._executions_queue: list[ExecuteSuccess[R] | ExecuteFail] = []
    self._pop_queue: list[Event] = []
    self._tasks_count: int = 0

  def add_a_task(self):
    with self._lock:
      self._tasks_count += 1

  def complete_task(self, target: ExecuteSuccess[R] | ExecuteFail):
    with self._lock:
      self._tasks_count -= 1
      self._executions_queue.append(target)
      if len(self._pop_queue) > 0:
        pop_event = self._pop_queue.pop(0)
        pop_event.set()

  def pop_result(self) -> ExecuteResult:
    while True:
      pop_event = Event()
      with self._lock:
        if len(self._executions_queue) > 0:
          return self._executions_queue.pop(0)
        if self._tasks_count <= len(self._pop_queue):
          return NoMoreExecutions()
        self._pop_queue.append(pop_event)
      pop_event.wait()

@dataclass
class _Worker:
  thread: Thread
  is_working: bool
  did_removed: bool

# [thread safe]
class ThreadPool(Generic[R]):
  def __init__(self, interruption: Interruption) -> None:
    self._interruption: Interruption = interruption
    self._lock: Lock = Lock()
    self._workers: list[_Worker] = []
    self._waker: Waker[None | Callable[[], R]] = Waker()
    self._results_queue: _ResultsQueue[R] = _ResultsQueue()

  @property
  def did_stop(self) -> bool:
    return self._waker.did_stop

  def workers(self) -> int:
    return len(self._workers)

  def set_workers(self, workers: int) -> None:
    to_start_threads: list[Thread] | None = None
    to_join_threads: list[Thread] | None = None

    with self._lock:
      if self._waker.did_stop:
        return

      if len(self._workers) < workers:
        to_added_workers = workers - len(self._workers)
        to_start_threads = []

        for _ in range(to_added_workers):
          worker = _Worker(
            thread=None,
            is_working=False,
            did_removed=False,
          )
          self._workers.append(worker)
          thread=Thread(
            target=self._run_in_background,
            args=(worker,),
          )
          worker.thread = thread
          to_start_threads.append(thread)

      elif len(self._workers) > workers:
        to_removed_workers = len(self._workers) - workers
        removed_indexes: set[int] = set()

        for want_is_working in (False, True):
          for i, worker in enumerate(self._workers):
            if len(removed_indexes) >= to_removed_workers:
              break
            if worker.is_working == want_is_working:
              removed_indexes.add(i)

        to_join_threads = []
        removed_workers = [
          worker for i, worker in enumerate(self._workers)
          if i in removed_indexes
        ]
        self._workers = [
          worker for i, worker in enumerate(self._workers)
          if i not in removed_indexes
        ]
        for removed_worker in removed_workers:
          removed_worker.did_removed = True
          to_join_threads.append(removed_worker.thread)

        self._waker.broadcast(None)

    if to_start_threads is not None:
      for thread in to_start_threads:
        thread.start()

    if to_join_threads is not None:
      for thread in to_join_threads:
        thread.join()

  def stop(self) -> None:
    workers: list[_Worker]
    with self._lock:
      if self._waker.did_stop:
        return
      self._waker.stop()
      workers = self._workers
      self._workers = []

    for worker in workers:
      worker.thread.join()

  def execute(self, func: Callable[[], R]) -> None:
    self._results_queue.add_a_task()
    self._waker.push(func)

  def pop_result(self) -> ExecuteResult:
    return self._results_queue.pop_result()

  def _run_in_background(self, worker: _Worker):
    with self._interruption.context():
      func: None | Callable[[], R] = None
      while True:
        if worker.did_removed:
          break
        try:
          func = self._waker.receive()
        except WakerDidStop:
          break
        if func is None:
          continue
        try:
          worker.is_working = True
          result = func()
          self._results_queue.complete_task(ExecuteSuccess(result=result))
        except Exception as e:
          traceback.print_exc()
          self._results_queue.complete_task(ExecuteFail(error=e))
        finally:
          worker.is_working = False