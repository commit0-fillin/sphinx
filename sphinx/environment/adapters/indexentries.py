"""Index entries adapters for sphinx.environment."""
from __future__ import annotations
import re
import unicodedata
from itertools import groupby
from typing import TYPE_CHECKING
from sphinx.errors import NoUri
from sphinx.locale import _, __
from sphinx.util import logging
from sphinx.util.index_entries import _split_into
if TYPE_CHECKING:
    from typing import Literal, TypeAlias
    from sphinx.builders import Builder
    from sphinx.environment import BuildEnvironment
    _IndexEntryTarget: TypeAlias = tuple[str | None, str | Literal[False]]
    _IndexEntryTargets: TypeAlias = list[_IndexEntryTarget]
    _IndexEntryCategoryKey: TypeAlias = str | None
    _IndexEntrySubItems: TypeAlias = dict[str, tuple[_IndexEntryTargets, _IndexEntryCategoryKey]]
    _IndexEntry: TypeAlias = tuple[_IndexEntryTargets, _IndexEntrySubItems, _IndexEntryCategoryKey]
    _IndexEntryMap: TypeAlias = dict[str, _IndexEntry]
    _Index: TypeAlias = list[tuple[str, list[tuple[str, tuple[_IndexEntryTargets, list[tuple[str, _IndexEntryTargets]], _IndexEntryCategoryKey]]]]]
logger = logging.getLogger(__name__)

class IndexEntries:

    def __init__(self, env: BuildEnvironment) -> None:
        self.env = env
        self.builder: Builder

    def create_index(self, builder: Builder, group_entries: bool=True, _fixre: re.Pattern[str]=re.compile('(.*) ([(][^()]*[)])')) -> _Index:
        """Create the real index from the collected index entries."""
        new = {}

        def add_entry(word: str, subword: str, main_entry: _IndexEntryTarget | None, 
                      location: _IndexEntryTarget, typ: str | None) -> None:
            entry = new.setdefault(word, ({}, {}, typ))
            if subword:
                entry[1].setdefault(subword, ([], typ))[0].append(location)
            elif main_entry:
                entry[0].append(location)

        for fn, entries in self.env.indexentries.items():
            for entry in entries:
                try:
                    main_entry, subentries = _split_into(2, 'pair', entry[0])
                except ValueError:
                    main_entry, = _split_into(1, 'single', entry[0])
                    subentries = ''
                try:
                    location = entry[1]
                    if len(location) == 3:
                        docname, ref_type, ref_id = location
                        typ = None
                    else:
                        docname, ref_type, ref_id, typ = location
                    if ref_type == 'inline':
                        location = (docname, ref_id)
                    else:
                        location = (docname, ref_type)
                except ValueError:
                    logger.warning(__('invalid index entry %r'), entry, location=fn)
                    continue

                m = _fixre.match(main_entry)
                if m:
                    main_entry = m.group(1)
                    key = unicodedata.normalize('NFD', m.group(2).strip())
                    key = ''.join(c for c in key if unicodedata.category(c) != 'Mn')
                    key = key.lower().strip()
                    add_entry(main_entry, subentries, None, location, key)
                else:
                    add_entry(main_entry, subentries, None, location, None)

        def _sort_and_group(entries: _IndexEntryMap, separated: bool) -> _Index:
            entries = sorted(entries.items(), key=_key_func_1)
            if separated:
                return [(key, list(group)) for key, group in groupby(entries, _group_by_func)]
            return [('', entries)]

        result = _sort_and_group(new, group_entries)
        for _, entries in result:
            for entry in entries:
                entry[1][0].sort(key=_key_func_0)
                for subentries in entry[1][1].values():
                    subentries[0].sort(key=_key_func_0)
                entry[1][1] = sorted(entry[1][1].items(), key=_key_func_2)

        return result

def _key_func_0(entry: _IndexEntryTarget) -> tuple[bool, str | Literal[False]]:
    """Sort the index entries for same keyword."""
    # Sort entries without a target to the end
    return (entry[1] is not None, entry[1] or '')

def _key_func_1(entry: tuple[str, _IndexEntry]) -> tuple[tuple[int, str], str]:
    """Sort the index entries"""
    key = entry[0].lower()
    if entry[1][2] is not None:
        # Sort entries with a key
        return ((0, entry[1][2]), key)
    else:
        # Sort entries without a key
        return ((1, key), key)

def _key_func_2(entry: tuple[str, _IndexEntryTargets]) -> str:
    """Sort the sub-index entries"""
    return entry[0].lower()

def _group_by_func(entry: tuple[str, _IndexEntry]) -> str:
    """Group the entries by letter or category key."""
    if entry[1][2] is not None:
        return entry[1][2]
    return entry[0][0].upper()
