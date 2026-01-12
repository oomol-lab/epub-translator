from collections import deque
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TypeVar

P = TypeVar("P")
R = TypeVar("R")


def run_concurrency(
    parameters: Iterable[P],
    execute: Callable[[P], R],
    concurrency: int,
) -> Iterable[R]:
    # Fast path: concurrency == 1, no thread overhead
    if concurrency == 1:
        for param in parameters:
            yield execute(param)
        return

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures: deque[Future[R]] = deque()
        params_iter = iter(parameters)

        for _ in range(concurrency):
            param = next(params_iter, None)
            if param is None:
                break
            future = executor.submit(execute, param)
            futures.append(future)

        while futures:
            future = futures.popleft()
            yield future.result()
            param = next(params_iter, None)
            if param is not None:
                new_future = executor.submit(execute, param)
                futures.append(new_future)
