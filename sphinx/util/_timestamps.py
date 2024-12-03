from __future__ import annotations
import time

def _format_rfc3339_microseconds(timestamp: int, /) -> str:
    """Return an RFC 3339 formatted string representing the given timestamp.

    :param timestamp: The timestamp to format, in microseconds.
    """
    seconds, microseconds = divmod(timestamp, 1_000_000)
    dt = time.gmtime(seconds)
    return (f"{dt.tm_year:04d}-{dt.tm_mon:02d}-{dt.tm_mday:02d}T"
            f"{dt.tm_hour:02d}:{dt.tm_min:02d}:{dt.tm_sec:02d}.{microseconds:06d}Z")
