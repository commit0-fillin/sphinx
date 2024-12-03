"""Convert times to and from HTTP-date serialisations.

Reference: https://www.rfc-editor.org/rfc/rfc7231#section-7.1.1.1
"""
import time
import warnings
from email.utils import parsedate_tz
from sphinx.deprecation import RemovedInSphinx90Warning
_WEEKDAY_NAME = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')
_MONTH_NAME = ('', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
_GMT_OFFSET = float(time.localtime().tm_gmtoff)

def epoch_to_rfc1123(epoch: float) -> str:
    """Return HTTP-date string from epoch offset."""
    t = time.gmtime(epoch)
    return time.strftime("%a, %d %b %Y %H:%M:%S GMT", t)

def rfc1123_to_epoch(rfc1123: str) -> float:
    """Return epoch offset from HTTP-date string."""
    t = parsedate_tz(rfc1123)
    if t is None:
        raise ValueError("Invalid RFC 1123 date format")
    return time.mktime(t[:9]) - _GMT_OFFSET
