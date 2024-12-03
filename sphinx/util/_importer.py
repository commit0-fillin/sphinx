from __future__ import annotations
from importlib import import_module
from typing import Any
from sphinx.errors import ExtensionError

def import_object(object_name: str, /, source: str='') -> Any:
    """Import python object by qualname."""
    try:
        module_name, object_name = object_name.rsplit('.', 1)
    except ValueError:
        raise ExtensionError(f"Invalid object name: {object_name}")

    try:
        module = import_module(module_name)
        return getattr(module, object_name)
    except ImportError as e:
        raise ExtensionError(f"Could not import {module_name}", orig_exc=e, modname=module_name)
    except AttributeError as e:
        raise ExtensionError(f"Could not find object {object_name} in module {module_name}", orig_exc=e, modname=module_name)
