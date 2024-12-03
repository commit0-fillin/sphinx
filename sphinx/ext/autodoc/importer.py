"""Importer utilities for autodoc"""
from __future__ import annotations
import contextlib
import importlib
import os
import sys
import traceback
import typing
from enum import Enum
from typing import TYPE_CHECKING, NamedTuple
from sphinx.errors import PycodeError
from sphinx.ext.autodoc.mock import ismock, undecorate
from sphinx.pycode import ModuleAnalyzer
from sphinx.util import logging
from sphinx.util.inspect import getannotations, getmro, getslots, isclass, isenumclass, safe_getattr, unwrap_all
if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping
    from types import ModuleType
    from typing import Any
    from sphinx.ext.autodoc import ObjectMember
logger = logging.getLogger(__name__)

def _filter_enum_dict(enum_class: type[Enum], attrgetter: Callable[[Any, str, Any], Any], enum_class_dict: Mapping[str, object]) -> Iterator[tuple[str, type, Any]]:
    """Find the attributes to document of an enumeration class.

    The output consists of triplets ``(attribute name, defining class, value)``
    where the attribute name can appear more than once during the iteration
    but with different defining class. The order of occurrence is guided by
    the MRO of *enum_class*.
    """
    for cls in enum_class.__mro__:
        for name, value in cls.__dict__.items():
            if name in enum_class_dict:
                yield name, cls, attrgetter(enum_class, name, value)

def mangle(subject: Any, name: str) -> str:
    """Mangle the given name."""
    try:
        if not name.startswith('__'):
            return name
        if name.endswith('__'):
            return name
        cls_name = subject.__name__
        return f"_{cls_name}{name}"
    except AttributeError:
        return name

def unmangle(subject: Any, name: str) -> str | None:
    """Unmangle the given name."""
    try:
        cls_name = subject.__name__
        if name.startswith(f"_{cls_name}__") and not name.endswith('__'):
            return f"__{name[len(cls_name) + 1:]}"
    except AttributeError:
        pass
    return None

def import_module(modname: str) -> Any:
    """Call importlib.import_module(modname), convert exceptions to ImportError."""
    try:
        return importlib.import_module(modname)
    except Exception as exc:
        raise ImportError(f"Could not import module '{modname}': {exc}") from exc

def _reload_module(module: ModuleType) -> Any:
    """
    Call importlib.reload(module), convert exceptions to ImportError
    """
    try:
        return importlib.reload(module)
    except Exception as exc:
        raise ImportError(f"Could not reload module '{module.__name__}': {exc}") from exc

class Attribute(NamedTuple):
    name: str
    directly_defined: bool
    value: Any

def get_object_members(subject: Any, objpath: list[str], attrgetter: Callable, analyzer: ModuleAnalyzer | None=None) -> dict[str, Attribute]:
    """Get members and attributes of target object."""
    members = {}
    
    # Get all members of the object
    for name in dir(subject):
        try:
            value = attrgetter(subject, name)
            directly_defined = analyzer.is_attribute_defined(objpath + [name]) if analyzer else True
            members[name] = Attribute(name, directly_defined, value)
        except Exception:
            continue

    # Handle special cases for classes
    if inspect.isclass(subject):
        # Add class variables
        for name, value in subject.__dict__.items():
            if name not in members:
                members[name] = Attribute(name, True, value)

        # Add inherited members
        for base in subject.__bases__:
            for name, attr in get_object_members(base, objpath, attrgetter, analyzer).items():
                if name not in members:
                    members[name] = Attribute(name, False, attr.value)

    return members

def get_class_members(subject: Any, objpath: Any, attrgetter: Callable, inherit_docstrings: bool=True) -> dict[str, ObjectMember]:
    """Get members and attributes of target class."""
    members = {}

    # Get all members of the class
    for name in dir(subject):
        try:
            value = attrgetter(subject, name)
            is_inherited = not hasattr(subject, name)
            
            # Handle docstring inheritance
            if inherit_docstrings and is_inherited and isinstance(value, (property, types.FunctionType)):
                orig_value = value
                for base in subject.__mro__[1:]:
                    if hasattr(base, name):
                        base_value = getattr(base, name)
                        if orig_value.__doc__ is None and base_value.__doc__:
                            value = base_value
                            break

            members[name] = ObjectMember(name, value, is_inherited)
        except Exception:
            continue

    # Add class variables
    for name, value in subject.__dict__.items():
        if name not in members:
            members[name] = ObjectMember(name, value, False)

    return members
