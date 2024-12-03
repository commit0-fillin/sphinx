"""Helpers for inspecting Python modules."""
from __future__ import annotations
import ast
import builtins
import contextlib
import enum
import inspect
import re
import sys
import types
import typing
from collections.abc import Mapping
from functools import cached_property, partial, partialmethod, singledispatchmethod
from importlib import import_module
from inspect import Parameter, Signature
from io import StringIO
from types import ClassMethodDescriptorType, MethodDescriptorType, WrapperDescriptorType
from typing import TYPE_CHECKING, Any, ForwardRef
from sphinx.pycode.ast import unparse as ast_unparse
from sphinx.util import logging
from sphinx.util.typing import stringify_annotation
if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from inspect import _ParameterKind
    from types import MethodType, ModuleType
    from typing import Final, Protocol, TypeAlias
    from typing_extensions import TypeIs

    class _SupportsGet(Protocol):

        def __get__(self, __instance: Any, __owner: type | None=...) -> Any:
            ...

    class _SupportsSet(Protocol):

        def __set__(self, __instance: Any, __value: Any) -> None:
            ...

    class _SupportsDelete(Protocol):

        def __delete__(self, __instance: Any) -> None:
            ...
    _RoutineType: TypeAlias = types.FunctionType | types.LambdaType | types.MethodType | types.BuiltinFunctionType | types.BuiltinMethodType | types.WrapperDescriptorType | types.MethodDescriptorType | types.ClassMethodDescriptorType
    _SignatureType: TypeAlias = Callable[..., Any] | staticmethod | classmethod
logger = logging.getLogger(__name__)
memory_address_re = re.compile(' at 0x[0-9a-f]{8,16}(?=>)', re.IGNORECASE)
isasyncgenfunction = inspect.isasyncgenfunction
ismethod = inspect.ismethod
ismethoddescriptor = inspect.ismethoddescriptor
isclass = inspect.isclass
ismodule = inspect.ismodule

def unwrap(obj: Any) -> Any:
    """Get an original object from wrapped object (wrapped functions).

    Mocked objects are returned as is.
    """
    if hasattr(obj, '__wrapped__'):
        return unwrap(obj.__wrapped__)
    return obj

def unwrap_all(obj: Any, *, stop: Callable[[Any], bool] | None=None) -> Any:
    """Get an original object from wrapped object.

    Unlike :func:`unwrap`, this unwraps partial functions, wrapped functions,
    class methods and static methods.

    When specified, *stop* is a predicate indicating whether an object should
    be unwrapped or not.
    """
    while True:
        if stop and stop(obj):
            return obj
        if hasattr(obj, '__wrapped__'):
            obj = obj.__wrapped__
        elif isinstance(obj, partial):
            obj = obj.func
        elif isinstance(obj, (classmethod, staticmethod)):
            obj = obj.__func__
        else:
            return obj

def getall(obj: Any) -> Sequence[str] | None:
    """Get the ``__all__`` attribute of an object as a sequence.

    This returns ``None`` if the given ``obj.__all__`` does not exist and
    raises :exc:`ValueError` if ``obj.__all__`` is not a list or tuple of
    strings.
    """
    try:
        all_attr = getattr(obj, '__all__')
    except AttributeError:
        return None
    
    if not isinstance(all_attr, (list, tuple)):
        raise ValueError("__all__ must be a list or tuple")
    
    if not all(isinstance(item, str) for item in all_attr):
        raise ValueError("__all__ must contain only strings")
    
    return all_attr

def getannotations(obj: Any) -> Mapping[str, Any]:
    """Safely get the ``__annotations__`` attribute of an object."""
    try:
        return obj.__annotations__
    except AttributeError:
        return {}

def getglobals(obj: Any) -> Mapping[str, Any]:
    """Safely get :attr:`obj.__globals__ <function.__globals__>`."""
    try:
        return obj.__globals__
    except AttributeError:
        return {}

def getmro(obj: Any) -> tuple[type, ...]:
    """Safely get :attr:`obj.__mro__ <class.__mro__>`."""
    try:
        return obj.__mro__
    except AttributeError:
        return ()

def getorigbases(obj: Any) -> tuple[Any, ...] | None:
    """Safely get ``obj.__orig_bases__``.

    This returns ``None`` if the object is not a class or if ``__orig_bases__``
    is not well-defined (e.g., a non-tuple object or an empty sequence).
    """
    if not isinstance(obj, type):
        return None
    try:
        orig_bases = obj.__orig_bases__
        if isinstance(orig_bases, tuple) and len(orig_bases) > 0:
            return orig_bases
    except AttributeError:
        pass
    return None

def getslots(obj: Any) -> dict[str, Any] | dict[str, None] | None:
    """Safely get :term:`obj.__slots__ <__slots__>` as a dictionary if any.

    - This returns ``None`` if ``obj.__slots__`` does not exist.
    - This raises a :exc:`TypeError` if *obj* is not a class.
    - This raises a :exc:`ValueError` if ``obj.__slots__`` is invalid.
    """
    if not isinstance(obj, type):
        raise TypeError("Expected a class object")
    
    try:
        slots = obj.__slots__
    except AttributeError:
        return None
    
    if isinstance(slots, str):
        return {slots: None}
    elif isinstance(slots, (list, tuple)):
        return {slot: None for slot in slots}
    else:
        raise ValueError("Invalid __slots__ attribute")

def isenumclass(x: Any) -> TypeIs[type[enum.Enum]]:
    """Check if the object is an :class:`enumeration class <enum.Enum>`."""
    return isinstance(x, type) and issubclass(x, enum.Enum)

def isenumattribute(x: Any) -> TypeIs[enum.Enum]:
    """Check if the object is an enumeration attribute."""
    return isinstance(x, enum.Enum)

def unpartial(obj: Any) -> Any:
    """Get an original object from a partial-like object.

    If *obj* is not a partial object, it is returned as is.

    .. seealso:: :func:`ispartial`
    """
    while ispartial(obj):
        obj = obj.func
    return obj

def ispartial(obj: Any) -> TypeIs[partial | partialmethod]:
    """Check if the object is a partial function or method."""
    return isinstance(obj, (partial, partialmethod))

def isclassmethod(obj: Any, cls: Any=None, name: str | None=None) -> TypeIs[classmethod]:
    """Check if the object is a :class:`classmethod`."""
    if isinstance(obj, classmethod):
        return True
    if cls and name:
        method = getattr(cls, name, None)
        return isinstance(method, classmethod)
    return False

def isstaticmethod(obj: Any, cls: Any=None, name: str | None=None) -> TypeIs[staticmethod]:
    """Check if the object is a :class:`staticmethod`."""
    if isinstance(obj, staticmethod):
        return True
    if cls and name:
        method = getattr(cls, name, None)
        return isinstance(method, staticmethod)
    return False

def isdescriptor(x: Any) -> TypeIs[_SupportsGet | _SupportsSet | _SupportsDelete]:
    """Check if the object is a :external+python:term:`descriptor`."""
    return (hasattr(x, '__get__') or
            hasattr(x, '__set__') or
            hasattr(x, '__delete__'))

def isabstractmethod(obj: Any) -> bool:
    """Check if the object is an :func:`abstractmethod`."""
    return getattr(obj, '__isabstractmethod__', False)

def isboundmethod(method: MethodType) -> bool:
    """Check if the method is a bound method."""
    return hasattr(method, '__self__') and method.__self__ is not None

def is_cython_function_or_method(obj: Any) -> bool:
    """Check if the object is a function or method in cython."""
    return type(obj).__name__ in ('cython_function_or_method', 'PyCFunction')
_DESCRIPTOR_LIKE: Final[tuple[type, ...]] = (ClassMethodDescriptorType, MethodDescriptorType, WrapperDescriptorType)

def isattributedescriptor(obj: Any) -> bool:
    """Check if the object is an attribute-like descriptor."""
    return (isdescriptor(obj) and
            not isinstance(obj, _DESCRIPTOR_LIKE) and
            not inspect.ismethod(obj) and
            not inspect.isfunction(obj) and
            not inspect.isclass(obj))

def is_singledispatch_function(obj: Any) -> bool:
    """Check if the object is a :func:`~functools.singledispatch` function."""
    return hasattr(obj, 'dispatch') and hasattr(obj, 'register')

def is_singledispatch_method(obj: Any) -> TypeIs[singledispatchmethod]:
    """Check if the object is a :class:`~functools.singledispatchmethod`."""
    return isinstance(obj, singledispatchmethod)

def isfunction(obj: Any) -> TypeIs[types.FunctionType]:
    """Check if the object is a user-defined function.

    Partial objects are unwrapped before checking them.

    .. seealso:: :external+python:func:`inspect.isfunction`
    """
    obj = unpartial(obj)
    return isinstance(obj, types.FunctionType)

def isbuiltin(obj: Any) -> TypeIs[types.BuiltinFunctionType]:
    """Check if the object is a built-in function or method.

    Partial objects are unwrapped before checking them.

    .. seealso:: :external+python:func:`inspect.isbuiltin`
    """
    obj = unpartial(obj)
    return isinstance(obj, types.BuiltinFunctionType)

def isroutine(obj: Any) -> TypeIs[_RoutineType]:
    """Check if the object is a kind of function or method.

    Partial objects are unwrapped before checking them.

    .. seealso:: :external+python:func:`inspect.isroutine`
    """
    obj = unpartial(obj)
    return isinstance(obj, (
        types.FunctionType,
        types.LambdaType,
        types.MethodType,
        types.BuiltinFunctionType,
        types.BuiltinMethodType,
        WrapperDescriptorType,
        MethodDescriptorType,
        ClassMethodDescriptorType
    ))

def iscoroutinefunction(obj: Any) -> TypeIs[Callable[..., types.CoroutineType]]:
    """Check if the object is a :external+python:term:`coroutine` function."""
    return inspect.iscoroutinefunction(obj) or _is_wrapped_coroutine(obj)

def _is_wrapped_coroutine(obj: Any) -> bool:
    """Check if the object is wrapped coroutine-function."""
    return (hasattr(obj, '__wrapped__') and
            inspect.iscoroutinefunction(obj.__wrapped__))

def isproperty(obj: Any) -> TypeIs[property | cached_property]:
    """Check if the object is property (possibly cached)."""
    return isinstance(obj, (property, cached_property))

def isgenericalias(obj: Any) -> TypeIs[types.GenericAlias]:
    """Check if the object is a generic alias."""
    return isinstance(obj, types.GenericAlias)

def safe_getattr(obj: Any, name: str, *defargs: Any) -> Any:
    """A getattr() that turns all exceptions into AttributeErrors."""
    try:
        return getattr(obj, name, *defargs)
    except Exception:
        # Turn all exceptions into AttributeError
        if defargs:
            return defargs[0]
        raise AttributeError(f"'{type(obj).__name__}' object has no attribute '{name}'")

def object_description(obj: Any, *, _seen: frozenset[int]=frozenset()) -> str:
    """A repr() implementation that returns text safe to use in reST context.

    Maintains a set of 'seen' object IDs to detect and avoid infinite recursion.
    """
    obj_id = id(obj)
    if obj_id in _seen:
        return '...'
    
    _seen = _seen | frozenset([obj_id])
    
    if isinstance(obj, str):
        return obj
    elif isinstance(obj, (list, tuple)):
        return '[' + ', '.join(object_description(x, _seen=_seen) for x in obj) + ']'
    elif isinstance(obj, dict):
        return '{' + ', '.join(f'{object_description(k, _seen=_seen)}: {object_description(v, _seen=_seen)}' 
                               for k, v in obj.items()) + '}'
    else:
        return memory_address_re.sub('', repr(obj))

def is_builtin_class_method(obj: Any, attr_name: str) -> bool:
    """Check whether *attr_name* is implemented on a builtin class.

        >>> is_builtin_class_method(int, '__init__')
        True


    This function is needed since CPython implements ``int.__init__`` via
    descriptors, but PyPy implementation is written in pure Python code.
    """
    try:
        mro = obj.__mro__
    except AttributeError:
        return False
    
    for cls in mro:
        if cls.__module__ == 'builtins' and hasattr(cls, attr_name):
            return True
    return False

class DefaultValue:
    """A simple wrapper for default value of the parameters of overload functions."""

    def __init__(self, value: str) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        return self.value == other

    def __repr__(self) -> str:
        return self.value

class TypeAliasForwardRef:
    """Pseudo typing class for :confval:`autodoc_type_aliases`.

    This avoids the error on evaluating the type inside :func:`typing.get_type_hints()`.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def __call__(self) -> None:
        return None

    def __eq__(self, other: Any) -> bool:
        return self.name == other

    def __hash__(self) -> int:
        return hash(self.name)

    def __repr__(self) -> str:
        return self.name

class TypeAliasModule:
    """Pseudo module class for :confval:`autodoc_type_aliases`."""

    def __init__(self, modname: str, mapping: Mapping[str, str]) -> None:
        self.__modname = modname
        self.__mapping = mapping
        self.__module: ModuleType | None = None

    def __getattr__(self, name: str) -> Any:
        fullname = '.'.join(filter(None, [self.__modname, name]))
        if fullname in self.__mapping:
            return TypeAliasForwardRef(self.__mapping[fullname])
        else:
            prefix = fullname + '.'
            nested = {k: v for k, v in self.__mapping.items() if k.startswith(prefix)}
            if nested:
                return TypeAliasModule(fullname, nested)
            else:
                try:
                    return import_module(fullname)
                except ImportError:
                    if self.__module is None:
                        self.__module = import_module(self.__modname)
                    return getattr(self.__module, name)

class TypeAliasNamespace(dict[str, Any]):
    """Pseudo namespace class for :confval:`autodoc_type_aliases`.

    Useful for looking up nested objects via ``namespace.foo.bar.Class``.
    """

    def __init__(self, mapping: Mapping[str, str]) -> None:
        super().__init__()
        self.__mapping = mapping

    def __getitem__(self, key: str) -> Any:
        if key in self.__mapping:
            return TypeAliasForwardRef(self.__mapping[key])
        else:
            prefix = key + '.'
            nested = {k: v for k, v in self.__mapping.items() if k.startswith(prefix)}
            if nested:
                return TypeAliasModule(key, nested)
            else:
                raise KeyError

def _should_unwrap(subject: _SignatureType) -> bool:
    """Check the function should be unwrapped on getting signature."""
    return (ispartial(subject) or
            (isclassmethod(subject) and isinstance(subject, classmethod)) or
            (isstaticmethod(subject) and isinstance(subject, staticmethod)))

def signature(subject: _SignatureType, bound_method: bool=False, type_aliases: Mapping[str, str] | None=None) -> Signature:
    """Return a Signature object for the given *subject*.

    :param bound_method: Specify *subject* is a bound method or not
    """
    if bound_method:
        subject = getattr(subject, '__func__', subject)

    try:
        sig = inspect.signature(subject)
    except ValueError:
        # some builtin functions don't have signatures
        return Signature()

    parameters = list(sig.parameters.values())
    return_annotation = sig.return_annotation

    if bound_method and len(parameters) > 0:
        parameters.pop(0)

    if type_aliases:
        parameters = [
            param.replace(annotation=stringify_annotation(param.annotation, type_aliases))
            for param in parameters
        ]
        return_annotation = stringify_annotation(return_annotation, type_aliases)

    return Signature(parameters, return_annotation=return_annotation)

def evaluate_signature(sig: Signature, globalns: dict[str, Any] | None=None, localns: dict[str, Any] | None=None) -> Signature:
    """Evaluate unresolved type annotations in a signature object."""
    def evaluate_annotation(annotation):
        if isinstance(annotation, str):
            return eval(annotation, globalns, localns)
        return annotation

    evaluated_params = [
        param.replace(annotation=evaluate_annotation(param.annotation))
        for param in sig.parameters.values()
    ]
    evaluated_return = evaluate_annotation(sig.return_annotation)

    return Signature(evaluated_params, return_annotation=evaluated_return)

def _evaluate_forwardref(ref: ForwardRef, globalns: dict[str, Any] | None, localns: dict[str, Any] | None) -> Any:
    """Evaluate a forward reference."""
    if sys.version_info >= (3, 9):
        return ref._evaluate(globalns, localns, frozenset())
    else:
        return ref._evaluate(globalns, localns)

def _evaluate(annotation: Any, globalns: dict[str, Any], localns: dict[str, Any]) -> Any:
    """Evaluate unresolved type annotation."""
    if isinstance(annotation, str):
        if annotation.startswith(('typing.', 'typing_extensions.')):
            annotation = annotation.split('.', 1)[1]
        try:
            return eval(annotation, globalns, localns)
        except NameError:
            return annotation
    elif isinstance(annotation, ForwardRef):
        return _evaluate_forwardref(annotation, globalns, localns)
    return annotation

def stringify_signature(sig: Signature, show_annotation: bool=True, show_return_annotation: bool=True, unqualified_typehints: bool=False) -> str:
    """Stringify a :class:`~inspect.Signature` object.

    :param show_annotation: If enabled, show annotations on the signature
    :param show_return_annotation: If enabled, show annotation of the return value
    :param unqualified_typehints: If enabled, show annotations as unqualified
                                  (ex. io.StringIO -> StringIO)
    """
    def format_parameter(param: Parameter) -> str:
        if param.default is Parameter.empty:
            if param.annotation is Parameter.empty or not show_annotation:
                return str(param.name)
            else:
                return f"{param.name}: {stringify_annotation(param.annotation, unqualified_typehints)}"
        else:
            if param.annotation is Parameter.empty or not show_annotation:
                return f"{param.name}={param.default!r}"
            else:
                return f"{param.name}: {stringify_annotation(param.annotation, unqualified_typehints)}={param.default!r}"

    params = [format_parameter(param) for param in sig.parameters.values()]
    s = f"({', '.join(params)})"

    if sig.return_annotation is not Parameter.empty and show_return_annotation:
        s += f" -> {stringify_annotation(sig.return_annotation, unqualified_typehints)}"

    return s

def signature_from_str(signature: str) -> Signature:
    """Create a :class:`~inspect.Signature` object from a string."""
    try:
        # Create a dummy function with the given signature
        exec(f"def dummy{signature}: pass")
        return inspect.signature(locals()['dummy'])
    except SyntaxError as e:
        raise ValueError(f"Invalid signature string: {signature}") from e

def signature_from_ast(node: ast.FunctionDef, code: str='') -> Signature:
    """Create a :class:`~inspect.Signature` object from an AST node."""
    def get_annotation(ann):
        if ann is None:
            return Parameter.empty
        return ast_unparse(ann, code)

    parameters = []
    for arg in node.args.args:
        kind = Parameter.POSITIONAL_OR_KEYWORD
        default = Parameter.empty
        annotation = get_annotation(arg.annotation)
        parameters.append(Parameter(arg.arg, kind, default=default, annotation=annotation))

    if node.args.vararg:
        parameters.append(Parameter(node.args.vararg.arg, Parameter.VAR_POSITIONAL,
                                    annotation=get_annotation(node.args.vararg.annotation)))

    for arg in node.args.kwonlyargs:
        parameters.append(Parameter(arg.arg, Parameter.KEYWORD_ONLY,
                                    annotation=get_annotation(arg.annotation)))

    if node.args.kwarg:
        parameters.append(Parameter(node.args.kwarg.arg, Parameter.VAR_KEYWORD,
                                    annotation=get_annotation(node.args.kwarg.annotation)))

    return_annotation = get_annotation(node.returns)

    return Signature(parameters, return_annotation=return_annotation)

def getdoc(obj: Any, attrgetter: Callable=safe_getattr, allow_inherited: bool=False, cls: Any=None, name: str | None=None) -> str | None:
    """Get the docstring for the object.

    This tries to obtain the docstring for some kind of objects additionally:

    * partial functions
    * inherited docstring
    * inherited decorated methods
    """
    doc = attrgetter(obj, '__doc__', None)
    if ispartial(obj) and doc == obj.func.__doc__:
        return getdoc(obj.func)

    if doc is None and allow_inherited:
        if cls and name:
            for parent in cls.__mro__[1:]:
                parent_obj = attrgetter(parent, name, None)
                if parent_obj is not None:
                    doc = getdoc(parent_obj, attrgetter)
                    if doc:
                        return doc
        elif isinstance(obj, (classmethod, staticmethod)):
            return getdoc(obj.__func__)
        elif isinstance(obj, property):
            return getdoc(obj.fget)

    return doc
