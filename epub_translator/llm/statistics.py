from threading import Lock


class Statistics:
    def __init__(self) -> None:
        self._value: int = 0
        self._lock: Lock = Lock()

    @property
    def value(self) -> int:
        with self._lock:
            return self._value

    def increase(self, amount: int = 1) -> None:
        with self._lock:
            self._value += amount
