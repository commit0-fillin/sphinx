"""The composite types for Sphinx."""
from __future__ import annotations
import dataclasses
import sys
import types
import typing
from collections.abc import Callable, Sequence
from contextvars import Context, ContextVar, Token
from struct import Struct
from typing import TYPE_CHECKING, Annotated, Any, ForwardRef, NewType, TypedDict, TypeVar, Union
from docutils import nodes
from docutils.parsers.rst.states import Inliner
from sphinx.util import logging
if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Final, Literal, Protocol, TypeAlias
    from typing_extensions import TypeIs
    from sphinx.application import Sphinx
    _RestifyMode: TypeAlias = Literal['fully-qualified-except-typing', 'smart']
    _StringifyMode: TypeAlias = Literal['fully-qualified-except-typing', 'fully-qualified', 'smart']
logger = logging.getLogger(__name__)
_INVALID_BUILTIN_CLASSES: Final[Mapping[object, str]] = {Context: 'contextvars.Context', ContextVar: 'contextvars.ContextVar', Token: 'contextvars.Token', Struct: 'struct.Struct', types.AsyncGeneratorType: 'types.AsyncGeneratorType', types.BuiltinFunctionType: 'types.BuiltinFunctionType', types.BuiltinMethodType: 'types.BuiltinMethodType', types.CellType: 'types.CellType', types.ClassMethodDescriptorType: 'types.ClassMethodDescriptorType', types.CodeType: 'types.CodeType', types.CoroutineType: 'types.CoroutineType', types.FrameType: 'types.FrameType', types.FunctionType: 'types.FunctionType', types.GeneratorType: 'types.GeneratorType', types.GetSetDescriptorType: 'types.GetSetDescriptorType', types.LambdaType: 'types.LambdaType', types.MappingProxyType: 'types.MappingProxyType', types.MemberDescriptorType: 'types.MemberDescriptorType', types.MethodDescriptorType: 'types.MethodDescriptorType', types.MethodType: 'types.MethodType', types.MethodWrapperType: 'types.MethodWrapperType', types.ModuleType: 'types.ModuleType', types.TracebackType: 'types.TracebackType', types.WrapperDescriptorType: 'types.WrapperDescriptorType'}

def is_invalid_builtin_class(obj: Any) -> bool:
    """Check *obj* is an invalid built-in class."""
    return obj in _INVALID_BUILTIN_CLASSES
TextlikeNode: TypeAlias = nodes.Text | nodes.TextElement
PathMatcher: TypeAlias = Callable[[str], bool]
if TYPE_CHECKING:

    class RoleFunction(Protocol):

        def __call__(self, name: str, rawtext: str, text: str, lineno: int, inliner: Inliner, /, options: dict[str, Any] | None=None, content: Sequence[str]=()) -> tuple[list[nodes.Node], list[nodes.system_message]]:
            ...
else:
    RoleFunction: TypeAlias = Callable[[str, str, str, int, Inliner, dict[str, Any], Sequence[str]], tuple[list[nodes.Node], list[nodes.system_message]]]
OptionSpec: TypeAlias = dict[str, Callable[[str], Any]]
TitleGetter: TypeAlias = Callable[[nodes.Node], str]
InventoryItem: TypeAlias = tuple[str, str, str, str]
Inventory: TypeAlias = dict[str, dict[str, InventoryItem]]

class ExtensionMetadata(TypedDict, total=False):
    """The metadata returned by an extension's ``setup()`` function.

    See :ref:`ext-metadata`.
    """
    version: str
    "The extension version (default: ``'unknown version'``)."
    env_version: int
    'An integer that identifies the version of env data added by the extension.'
    parallel_read_safe: bool
    'Indicate whether parallel reading of source files is supported\n    by the extension.\n    '
    parallel_write_safe: bool
    'Indicate whether parallel writing of output files is supported\n    by the extension (default: ``True``).\n    '
if TYPE_CHECKING:
    _ExtensionSetupFunc: TypeAlias = Callable[[Sphinx], ExtensionMetadata]

def get_type_hints(obj: Any, globalns: dict[str, Any] | None=None, localns: dict[str, Any] | None=None, include_extras: bool=False) -> dict[str, Any]:
    """Return a dictionary containing type hints for a function, method, module or class
    object.

    This is a simple wrapper of `typing.get_type_hints()` that does not raise an error on
    runtime.
    """
    try:
        return typing.get_type_hints(obj, globalns, localns, include_extras)
    except Exception:
        return {}

def is_system_TypeVar(typ: Any) -> bool:
    """Check *typ* is system defined TypeVar."""
    return isinstance(typ, TypeVar) and typ.__module__ == 'typing'

def _is_annotated_form(obj: Any) -> TypeIs[Annotated[Any, ...]]:
    """Check if *obj* is an annotated type."""
    return isinstance(obj, type(Annotated[int, "metadata"]))

def _is_unpack_form(obj: Any) -> bool:
    """Check if the object is :class:`typing.Unpack` or equivalent."""
    return getattr(obj, "__origin__", None) is getattr(typing, "Unpack", None)

def restify(cls: Any, mode: _RestifyMode='fully-qualified-except-typing') -> str:
    """Convert a type-like object to a reST reference.

    :param mode: Specify a method how annotations will be stringified.

                 'fully-qualified-except-typing'
                     Show the module name and qualified name of the annotation except
                     the "typing" module.
                 'smart'
                     Show the name of the annotation.
    """
    if isinstance(cls, str):
        return cls
    elif isinstance(cls, type):
        if mode == 'smart':
            return cls.__name__
        else:
            module = cls.__module__
            name = cls.__qualname__
            if module == 'typing' or module == 'types':
                return name
            else:
                return f'{module}.{name}'
    elif cls is None:
        return 'None'
    else:
        return str(cls)

def stringify_annotation(annotation: Any, /, mode: _StringifyMode='fully-qualified-except-typing') -> str:
    """Stringify type annotation object.

    :param annotation: The annotation to stringified.
    :param mode: Specify a method how annotations will be stringified.

                 'fully-qualified-except-typing'
                     Show the module name and qualified name of the annotation except
                     the "typing" module.
                 'smart'
                     Show the name of the annotation.
                 'fully-qualified'
                     Show the module name and qualified name of the annotation.
    """
    if isinstance(annotation, str):
        return annotation
    elif isinstance(annotation, type):
        if mode == 'smart':
            return annotation.__name__
        elif mode == 'fully-qualified':
            return f'{annotation.__module__}.{annotation.__qualname__}'
        else:  # fully-qualified-except-typing
            if annotation.__module__ == 'typing':
                return annotation.__qualname__
            else:
                return f'{annotation.__module__}.{annotation.__qualname__}'
    elif annotation is None:
        return 'None'
    elif _is_annotated_form(annotation):
        return stringify_annotation(annotation.__origin__, mode=mode)
    elif _is_unpack_form(annotation):
        return f'Unpack[{stringify_annotation(annotation.__args__[0], mode=mode)}]'
    else:
        return str(annotation)
_DEPRECATED_OBJECTS: dict[str, tuple[Any, str, tuple[int, int]]] = {}

def __getattr__(name: str) -> Any:
    if name not in _DEPRECATED_OBJECTS:
        msg = f'module {__name__!r} has no attribute {name!r}'
        raise AttributeError(msg)
    from sphinx.deprecation import _deprecation_warning
    deprecated_object, canonical_name, remove = _DEPRECATED_OBJECTS[name]
    _deprecation_warning(__name__, name, canonical_name, remove=remove)
    return deprecated_object
