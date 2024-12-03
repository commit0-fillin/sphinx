from __future__ import annotations
import sys
import traceback
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING
from sphinx.errors import SphinxParallelError
from sphinx.util.console import strip_escape_sequences
if TYPE_CHECKING:
    from sphinx.application import Sphinx

def save_traceback(app: Sphinx | None, exc: BaseException) -> str:
    """Save the given exception's traceback in a temporary file."""
    with NamedTemporaryFile('w', delete=False, suffix='.log') as f:
        traceback.print_exc(file=f)
        return f.name

def format_exception_cut_frames(x: int=1) -> str:
    """Format an exception with traceback, but only the last x frames."""
    type_, value, tb = sys.exc_info()
    if tb is None:
        return ''
    
    # Get the last x frames
    tb_list = traceback.extract_tb(tb)
    last_frames = tb_list[-x:]
    
    # Format the exception and the last x frames
    lines = traceback.format_exception_only(type_, value)
    lines += traceback.format_list(last_frames)
    
    return ''.join(lines)
