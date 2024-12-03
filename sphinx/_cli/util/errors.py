from __future__ import annotations
import re
import sys
import tempfile
from typing import TYPE_CHECKING, TextIO
from sphinx.errors import SphinxParallelError
if TYPE_CHECKING:
    from sphinx.application import Sphinx
_ANSI_COLOUR_CODES: re.Pattern[str] = re.compile('\x1b.*?m')

def terminal_safe(s: str, /) -> str:
    """Safely encode a string for printing to the terminal."""
    return s.encode('ascii', 'backslashreplace').decode('ascii')

def save_traceback(app: Sphinx | None, exc: BaseException) -> str:
    """Save the given exception's traceback in a temporary file."""
    import traceback
    import tempfile
    
    fd, path = tempfile.mkstemp('.log', 'sphinx-err-')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(f'The full traceback has been saved in {path}\n')
        traceback.print_exc(file=f)
    
    return path
