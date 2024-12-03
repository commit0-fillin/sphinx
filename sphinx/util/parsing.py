"""Docutils utility functions for parsing text."""
from __future__ import annotations
import contextlib
from typing import TYPE_CHECKING
from docutils.nodes import Element, Node
from docutils.statemachine import StringList, string2lines
if TYPE_CHECKING:
    from collections.abc import Iterator
    from docutils.parsers.rst.states import RSTState

def nested_parse_to_nodes(state: RSTState, text: str | StringList, *, source: str='<generated text>', offset: int=0, allow_section_headings: bool=True, keep_title_context: bool=False) -> list[Node]:
    """Parse *text* into nodes.

    :param state:
        The state machine state. Must be a subclass of ``RSTState``.
    :param text:
        Text, in string form. ``StringList`` is also accepted.
    :param source:
        The text's source, used when creating a new ``StringList``.
    :param offset:
        The offset of the content.
    :param allow_section_headings:
        Are titles (sections) allowed in *text*?
        Note that this option bypasses Docutils' usual checks on
        doctree structure, and misuse of this option can lead to
        an incoherent doctree. In Docutils, section nodes should
        only be children of ``Structural`` nodes, which includes
        ``document``, ``section``, and ``sidebar`` nodes.
    :param keep_title_context:
        If this is False (the default), then *content* is parsed as if it were
        an independent document, meaning that title decorations (e.g. underlines)
        do not need to match the surrounding document.
        This is useful when the parsed content comes from
        a completely different context, such as docstrings.
        If this is True, then title underlines must match those in
        the surrounding document, otherwise the behaviour is undefined.

    .. versionadded:: 7.4
    """
    if isinstance(text, str):
        text = StringList(string2lines(text), source=source)
    elif isinstance(text, StringList):
        text.source = source

    memo = state.memo
    old_allow_section_headings = memo.allow_section_headings
    old_title_context = memo.title_context

    try:
        if not allow_section_headings:
            memo.allow_section_headings = False

        if not keep_title_context:
            memo.title_context = None

        node = Element()
        node.source = source
        node.line = offset + 1

        with contextlib.suppress(state.nested_parse):
            state.nested_parse(text, offset, node)

        return node.children
    finally:
        memo.allow_section_headings = old_allow_section_headings
        memo.title_context = old_title_context
