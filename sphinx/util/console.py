"""Format colored console output."""
from __future__ import annotations
import os
import re
import shutil
import sys
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Final
try:
    import colorama
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False
_CSI: Final[str] = re.escape('\x1b[')
_ansi_color_re: Final[re.Pattern[str]] = re.compile('\\x1b\\[(?:\\d+;){0,2}\\d*m')
_ansi_re: Final[re.Pattern[str]] = re.compile(_CSI + "\n    (?:\n      (?:\\d+;){0,2}\\d*m     # ANSI color code    ('m' is equivalent to '0m')\n    |\n      [012]?K               # ANSI Erase in Line ('K' is equivalent to '0K')\n    )", re.VERBOSE | re.ASCII)
'Pattern matching ANSI CSI colors (SGR) and erase line (EL) sequences.\n\nSee :func:`strip_escape_sequences` for details.\n'
codes: dict[str, str] = {}

def terminal_safe(s: str) -> str:
    """Safely encode a string for printing to the terminal."""
    return s.encode('ascii', 'replace').decode('ascii')

def get_terminal_width() -> int:
    """Return the width of the terminal in columns."""
    try:
        return shutil.get_terminal_size().columns
    except AttributeError:
        return 80  # Default width if unable to determine
_tw: int = get_terminal_width()

def strip_colors(s: str) -> str:
    """Remove the ANSI color codes in a string *s*.

    .. caution::

       This function is not meant to be used in production and should only
       be used for testing Sphinx's output messages.

    .. seealso:: :func:`strip_escape_sequences`
    """
    return _ansi_color_re.sub('', s)

def strip_escape_sequences(text: str, /) -> str:
    """Remove the ANSI CSI colors and "erase in line" sequences.

    Other `escape sequences `__ (e.g., VT100-specific functions) are not
    supported and only control sequences *natively* known to Sphinx (i.e.,
    colors declared in this module and "erase entire line" (``'\\x1b[2K'``))
    are eliminated by this function.

    .. caution::

       This function is not meant to be used in production and should only
       be used for testing Sphinx's output messages that were not tempered
       with by third-party extensions.

    .. versionadded:: 7.3

       This function is added as an *experimental* feature.

    __ https://en.wikipedia.org/wiki/ANSI_escape_code
    """
    return _ansi_re.sub('', text)
_attrs = {'reset': '39;49;00m', 'bold': '01m', 'faint': '02m', 'standout': '03m', 'underline': '04m', 'blink': '05m'}
for __name, __value in _attrs.items():
    codes[__name] = '\x1b[' + __value
_colors = [('black', 'darkgray'), ('darkred', 'red'), ('darkgreen', 'green'), ('brown', 'yellow'), ('darkblue', 'blue'), ('purple', 'fuchsia'), ('turquoise', 'teal'), ('lightgray', 'white')]
for __i, (__dark, __light) in enumerate(_colors, 30):
    codes[__dark] = '\x1b[%im' % __i
    codes[__light] = '\x1b[%im' % (__i + 60)
_orig_codes = codes.copy()
for _name in codes:
    create_color_func(_name)
