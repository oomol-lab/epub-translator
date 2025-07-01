from typing import Callable

ReportProgress = Callable[[float], None]
Translate=Callable[[list[str], ReportProgress], list[str]]