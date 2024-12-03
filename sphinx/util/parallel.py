"""Parallel building utilities."""
from __future__ import annotations
import os
import time
import traceback
from math import sqrt
from typing import TYPE_CHECKING, Any
try:
    import multiprocessing
    HAS_MULTIPROCESSING = True
except ImportError:
    HAS_MULTIPROCESSING = False
from sphinx.errors import SphinxParallelError
from sphinx.util import logging
if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
logger = logging.getLogger(__name__)
parallel_available = HAS_MULTIPROCESSING and os.name == 'posix'

class SerialTasks:
    """Has the same interface as ParallelTasks, but executes tasks directly."""

    def __init__(self, nproc: int=1) -> None:
        pass

class ParallelTasks:
    """Executes *nproc* tasks in parallel after forking."""

    def __init__(self, nproc: int) -> None:
        self.nproc = nproc
        self._result_funcs: dict[int, Callable] = {}
        self._args: dict[int, list[Any] | None] = {}
        self._procs: dict[int, Any] = {}
        self._precvs: dict[int, Any] = {}
        self._precvsWaiting: dict[int, Any] = {}
        self._pworking = 0
        self._taskid = 0
