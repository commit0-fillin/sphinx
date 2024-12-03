"""Utilities for docstring processing."""
from __future__ import annotations
import re
import sys
from docutils.parsers.rst.states import Body
field_list_item_re = re.compile(Body.patterns['field_marker'])

def separate_metadata(s: str | None) -> tuple[str | None, dict[str, str]]:
    """Separate docstring into metadata and others."""
    if s is None:
        return None, {}
    
    lines = s.split('\n')
    metadata = {}
    content = []
    in_metadata = True
    
    for line in lines:
        match = field_list_item_re.match(line)
        if match and in_metadata:
            key, value = match.group(1).strip(), match.group(2).strip()
            metadata[key] = value
        else:
            in_metadata = False
            content.append(line)
    
    return '\n'.join(content).strip() or None, metadata

def prepare_docstring(s: str, tabsize: int=8) -> list[str]:
    """Convert a docstring into lines of parseable reST.  Remove common leading
    indentation, where the indentation of the first line is ignored.

    Return the docstring as a list of lines usable for inserting into a docutils
    ViewList (used as argument of nested_parse().)  An empty line is added to
    act as a separator between this docstring and following content.
    """
    if not s:
        return []
    
    lines = s.expandtabs(tabsize).split('\n')
    
    # Find minimum indentation (first line doesn't count)
    indent = sys.maxsize
    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped:
            indent = min(indent, len(line) - len(stripped))
    
    # Remove indentation (first line is special)
    trimmed = [lines[0].strip()]
    if indent < sys.maxsize:
        for line in lines[1:]:
            trimmed.append(line[indent:].rstrip())
    
    # Strip off trailing and leading blank lines
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    while trimmed and not trimmed[0]:
        trimmed.pop(0)
    
    # Add an empty line to act as a separator
    trimmed.append('')
    
    return trimmed

def prepare_commentdoc(s: str) -> list[str]:
    """Extract documentation comment lines (starting with #:) and return them
    as a list of lines.  Returns an empty list if there is no documentation.
    """
    result = []
    for line in s.split('\n'):
        line = line.strip()
        if line.startswith('#:'):
            result.append(line[2:].strip())
        elif line.startswith('#') and line[1:].strip().startswith(':'):
            result.append(line.split(':', 1)[1].strip())
    return result
