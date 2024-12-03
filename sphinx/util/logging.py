"""Logging utility functions for Sphinx."""
from __future__ import annotations
import logging
import logging.handlers
from collections import defaultdict
from contextlib import contextmanager, nullcontext
from typing import IO, TYPE_CHECKING, Any
from docutils import nodes
from docutils.utils import get_source_line
from sphinx.errors import SphinxWarning
from sphinx.util.console import colorize
from sphinx.util.osutil import abspath
if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence, Set
    from typing import NoReturn
    from docutils.nodes import Node
    from sphinx.application import Sphinx
NAMESPACE = 'sphinx'
VERBOSE = 15
LEVEL_NAMES: defaultdict[str, int] = defaultdict(lambda: logging.WARNING, {'CRITICAL': logging.CRITICAL, 'SEVERE': logging.CRITICAL, 'ERROR': logging.ERROR, 'WARNING': logging.WARNING, 'INFO': logging.INFO, 'VERBOSE': VERBOSE, 'DEBUG': logging.DEBUG})
VERBOSITY_MAP: defaultdict[int, int] = defaultdict(lambda: logging.NOTSET, {0: logging.INFO, 1: VERBOSE, 2: logging.DEBUG})
COLOR_MAP: defaultdict[int, str] = defaultdict(lambda: 'blue', {logging.ERROR: 'darkred', logging.WARNING: 'red', logging.DEBUG: 'darkgray'})

def getLogger(name: str) -> SphinxLoggerAdapter:
    """Get logger wrapped by :class:`sphinx.util.logging.SphinxLoggerAdapter`.

    Sphinx logger always uses ``sphinx.*`` namespace to be independent from
    settings of root logger.  It ensures logging is consistent even if a
    third-party extension or imported application resets logger settings.

    Example usage::

        >>> from sphinx.util import logging
        >>> logger = logging.getLogger(__name__)
        >>> logger.info('Hello, this is an extension!')
        Hello, this is an extension!
    """
    logger = logging.getLogger(NAMESPACE + '.' + name)
    return SphinxLoggerAdapter(logger, {})

def convert_serializable(records: list[logging.LogRecord]) -> None:
    """Convert LogRecord serializable."""
    for record in records:
        record.args = tuple(repr(arg) for arg in record.args)
        record.exc_info = None
        record.exc_text = None

class SphinxLogRecord(logging.LogRecord):
    """Log record class supporting location"""
    prefix = ''
    location: Any = None

class SphinxInfoLogRecord(SphinxLogRecord):
    """Info log record class supporting location"""
    prefix = ''

class SphinxWarningLogRecord(SphinxLogRecord):
    """Warning log record class supporting location"""

class SphinxLoggerAdapter(logging.LoggerAdapter):
    """LoggerAdapter allowing ``type`` and ``subtype`` keywords."""
    KEYWORDS = ['type', 'subtype', 'location', 'nonl', 'color', 'once']

    def warning(self, msg: object, *args: object, type: None | str=None, subtype: None | str=None, location: None | str | tuple[str | None, int | None] | Node=None, nonl: bool=True, color: str | None=None, once: bool=False, **kwargs: Any) -> None:
        """Log a sphinx warning.

        It is recommended to include a ``type`` and ``subtype`` for warnings as
        these can be displayed to the user using :confval:`show_warning_types`
        and used in :confval:`suppress_warnings` to suppress specific warnings.

        It is also recommended to specify a ``location`` whenever possible
        to help users in correcting the warning.

        :param msg: The message, which may contain placeholders for ``args``.
        :param args: The arguments to substitute into ``msg``.
        :param type: The type of the warning.
        :param subtype: The subtype of the warning.
        :param location: The source location of the warning's origin,
            which can be a string (the ``docname`` or ``docname:lineno``),
            a tuple of ``(docname, lineno)``,
            or the docutils node object.
        :param nonl: Whether to append a new line terminator to the message.
        :param color: A color code for the message.
        :param once: Do not log this warning,
            if a previous warning already has same ``msg``, ``args`` and ``once=True``.
        """
        kwargs.update(type=type, subtype=subtype, location=location, nonl=nonl, color=color, once=once)
        for key in self.KEYWORDS:
            kwargs.setdefault(key, None)
        self.logger.warning(msg, *args, extra=kwargs)

class WarningStreamHandler(logging.StreamHandler):
    """StreamHandler for warnings."""
    pass

class NewLineStreamHandler(logging.StreamHandler):
    """StreamHandler which switches line terminator by record.nonl flag."""

class MemoryHandler(logging.handlers.BufferingHandler):
    """Handler buffering all logs."""
    buffer: list[logging.LogRecord]

    def __init__(self) -> None:
        super().__init__(-1)

@contextmanager
def pending_warnings() -> Iterator[logging.Handler]:
    """Context manager to postpone logging warnings temporarily.

    Similar to :func:`pending_logging`.
    """
    logger = logging.getLogger(NAMESPACE)
    memhandler = MemoryHandler()
    memhandler.setLevel(logging.WARNING)
    logger.addHandler(memhandler)
    try:
        yield memhandler
    finally:
        logger.removeHandler(memhandler)
        memhandler.flushTo(logger)

@contextmanager
def suppress_logging() -> Iterator[MemoryHandler]:
    """Context manager to suppress logging all logs temporarily.

    For example::

        >>> with suppress_logging():
        >>>     logger.warning('Warning message!')  # suppressed
        >>>     some_long_process()
        >>>
    """
    logger = logging.getLogger(NAMESPACE)
    memhandler = MemoryHandler()
    logger.addHandler(memhandler)
    logger.propagate = False
    try:
        yield memhandler
    finally:
        logger.removeHandler(memhandler)
        logger.propagate = True

@contextmanager
def pending_logging() -> Iterator[MemoryHandler]:
    """Context manager to postpone logging all logs temporarily.

    For example::

        >>> with pending_logging():
        >>>     logger.warning('Warning message!')  # not flushed yet
        >>>     some_long_process()
        >>>
        Warning message!  # the warning is flushed here
    """
    logger = logging.getLogger(NAMESPACE)
    memhandler = MemoryHandler()
    logger.addHandler(memhandler)
    try:
        yield memhandler
    finally:
        logger.removeHandler(memhandler)
        memhandler.flushTo(logger)
skip_warningiserror = nullcontext

@contextmanager
def prefixed_warnings(prefix: str) -> Iterator[None]:
    """Context manager to prepend prefix to all warning log records temporarily.

    For example::

        >>> with prefixed_warnings("prefix:"):
        >>>     logger.warning('Warning message!')  # => prefix: Warning message!

    .. versionadded:: 2.0
    """
    logger = logging.getLogger(NAMESPACE)
    prefix_filter = MessagePrefixFilter(prefix)
    logger.addFilter(prefix_filter)
    try:
        yield
    finally:
        logger.removeFilter(prefix_filter)

class LogCollector:

    def __init__(self) -> None:
        self.logs: list[logging.LogRecord] = []

class InfoFilter(logging.Filter):
    """Filter error and warning messages."""

class _RaiseOnWarningFilter(logging.Filter):
    """Raise exception if a warning is emitted."""

def is_suppressed_warning(warning_type: str, sub_type: str, suppress_warnings: Set[str] | Sequence[str]) -> bool:
    """Check whether the warning is suppressed or not."""
    if warning_type is None:
        return False

    for suppress in suppress_warnings:
        if suppress == warning_type:
            return True
        if sub_type and suppress == f"{warning_type}.{sub_type}":
            return True
    return False

class WarningSuppressor(logging.Filter):
    """Filter logs by `suppress_warnings`."""

    def __init__(self, app: Sphinx) -> None:
        self.app = app
        super().__init__()
        self.suppress_warnings = set(app.config.suppress_warnings)

class MessagePrefixFilter(logging.Filter):
    """Prepend prefix to all log records."""

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        super().__init__()

class OnceFilter(logging.Filter):
    """Show the message only once."""

    def __init__(self, name: str='') -> None:
        super().__init__(name)
        self.messages: dict[str, list] = {}

class SphinxLogRecordTranslator(logging.Filter):
    """Converts a log record to one Sphinx expects

    * Make a instance of SphinxLogRecord
    * docname to path if location given
    * append warning type/subtype to message if :confval:`show_warning_types` is ``True``
    """
    LogRecordClass: type[logging.LogRecord]

    def __init__(self, app: Sphinx) -> None:
        self.app = app
        super().__init__()

class InfoLogRecordTranslator(SphinxLogRecordTranslator):
    """LogRecordTranslator for INFO level log records."""
    LogRecordClass = SphinxInfoLogRecord

class WarningLogRecordTranslator(SphinxLogRecordTranslator):
    """LogRecordTranslator for WARNING level log records."""
    LogRecordClass = SphinxWarningLogRecord

class ColorizeFormatter(logging.Formatter):
    pass

class SafeEncodingWriter:
    """Stream writer which ignores UnicodeEncodeError silently"""

    def __init__(self, stream: IO) -> None:
        self.stream = stream
        self.encoding = getattr(stream, 'encoding', 'ascii') or 'ascii'

class LastMessagesWriter:
    """Stream writer storing last 10 messages in memory to save trackback"""

    def __init__(self, app: Sphinx, stream: IO) -> None:
        self.app = app

def setup(app: Sphinx, status: IO, warning: IO) -> None:
    """Setup root logger for Sphinx"""
    logger = logging.getLogger(NAMESPACE)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # Status handler
    status_handler = NewLineStreamHandler(stream=status)
    status_handler.setLevel(VERBOSITY_MAP[app.verbosity])
    status_handler.addFilter(InfoFilter())
    status_handler.setFormatter(ColorizeFormatter())
    logger.addHandler(status_handler)

    # Warning handler
    warning_handler = WarningStreamHandler(stream=warning)
    warning_handler.setLevel(logging.WARNING)
    warning_handler.setFormatter(ColorizeFormatter())
    logger.addHandler(warning_handler)

    # Add warning suppressor
    logger.addFilter(WarningSuppressor(app))

    # Add SphinxLogRecordTranslator
    logger.addFilter(SphinxLogRecordTranslator(app))
