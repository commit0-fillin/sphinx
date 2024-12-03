"""Operating system-related utility functions for Sphinx."""
from __future__ import annotations
import contextlib
import filecmp
import os
import re
import shutil
import sys
import unicodedata
from io import StringIO
from os import path
from pathlib import Path
from typing import TYPE_CHECKING
from sphinx.locale import __
if TYPE_CHECKING:
    from types import TracebackType
    from typing import Any
SEP = '/'

def canon_path(native_path: str | os.PathLike[str], /) -> str:
    """Return path in OS-independent form"""
    return str(Path(native_path).as_posix())

def path_stabilize(filepath: str | os.PathLike[str], /) -> str:
    """Normalize path separator and unicode string"""
    return unicodedata.normalize('NFC', str(Path(filepath)))

def relative_uri(base: str, to: str) -> str:
    """Return a relative URL from ``base`` to ``to``."""
    b = Path(base)
    t = Path(to)
    try:
        return str(t.relative_to(b))
    except ValueError:
        return str(t)

def ensuredir(file: str | os.PathLike[str]) -> None:
    """Ensure that a path exists."""
    Path(file).mkdir(parents=True, exist_ok=True)

def _last_modified_time(source: str | os.PathLike[str], /) -> int:
    """Return the last modified time of ``filename``.

    The time is returned as integer microseconds.
    The lowest common denominator of modern file-systems seems to be
    microsecond-level precision.

    We prefer to err on the side of re-rendering a file,
    so we round up to the nearest microsecond.
    """
    mtime = Path(source).stat().st_mtime
    return int(math.ceil(mtime * 1_000_000))

def _copy_times(source: str | os.PathLike[str], dest: str | os.PathLike[str]) -> None:
    """Copy a file's modification times."""
    st = os.stat(source)
    os.utime(dest, (st.st_atime, st.st_mtime))

def copyfile(source: str | os.PathLike[str], dest: str | os.PathLike[str], *, force: bool=False) -> None:
    """Copy a file and its modification times, if possible.

    :param source: An existing source to copy.
    :param dest: The destination path.
    :param bool force: Overwrite the destination file even if it exists.
    :raise FileNotFoundError: The *source* does not exist.

    .. note:: :func:`copyfile` is a no-op if *source* and *dest* are identical.
    """
    source_path = Path(source)
    dest_path = Path(dest)
    
    if not source_path.exists():
        raise FileNotFoundError(f"Source file {source} does not exist")
    
    if source_path.samefile(dest_path):
        return
    
    if dest_path.exists() and not force:
        return
    
    shutil.copy2(source_path, dest_path)
_no_fn_re = re.compile('[^a-zA-Z0-9_-]')

def relpath(path: str | os.PathLike[str], start: str | os.PathLike[str] | None=os.curdir) -> str:
    """Return a relative filepath to *path* either from the current directory or
    from an optional *start* directory.

    This is an alternative of ``os.path.relpath()``.  This returns original path
    if *path* and *start* are on different drives (for Windows platform).
    """
    try:
        return os.path.relpath(path, start)
    except ValueError:
        return str(path)
safe_relpath = relpath
fs_encoding = sys.getfilesystemencoding() or sys.getdefaultencoding()
abspath = path.abspath

class _chdir:
    """Remove this fall-back once support for Python 3.10 is removed."""

    def __init__(self, target_dir: str, /) -> None:
        self.path = target_dir
        self._dirs: list[str] = []

    def __enter__(self) -> None:
        self._dirs.append(os.getcwd())
        os.chdir(self.path)

    def __exit__(self, type: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None, /) -> None:
        os.chdir(self._dirs.pop())
if sys.version_info[:2] < (3, 11):
    cd = _chdir

class FileAvoidWrite:
    """File-like object that buffers output and only writes if content changed.

    Use this class like when writing to a file to avoid touching the original
    file if the content hasn't changed. This is useful in scenarios where file
    mtime is used to invalidate caches or trigger new behavior.

    When writing to this file handle, all writes are buffered until the object
    is closed.

    Objects can be used as context managers.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = path
        self._io: StringIO | None = None

    def close(self) -> None:
        """Stop accepting writes and write file, if needed."""
        if self._io is None:
            return

        content = self._io.getvalue()
        self._io.close()
        self._io = None

        if os.path.exists(self._path):
            with open(self._path, 'r', encoding='utf-8') as f:
                if f.read() == content:
                    return

        with open(self._path, 'w', encoding='utf-8') as f:
            f.write(content)

    def __enter__(self) -> FileAvoidWrite:
        return self

    def __exit__(self, exc_type: type[Exception], exc_value: Exception, traceback: Any) -> bool:
        self.close()
        return True

    def __getattr__(self, name: str) -> Any:
        if not self._io:
            msg = 'Must write to FileAvoidWrite before other methods can be used'
            raise Exception(msg)
        return getattr(self._io, name)
