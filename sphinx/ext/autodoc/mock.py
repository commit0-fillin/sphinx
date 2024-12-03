"""mock for autodoc"""
from __future__ import annotations
import contextlib
import os
import sys
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec
from types import MethodType, ModuleType
from typing import TYPE_CHECKING
from sphinx.util import logging
from sphinx.util.inspect import isboundmethod, safe_getattr
if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from typing import Any
    from typing_extensions import TypeIs
logger = logging.getLogger(__name__)

class _MockObject:
    """Used by autodoc_mock_imports."""
    __display_name__ = '_MockObject'
    __name__ = ''
    __sphinx_mock__ = True
    __sphinx_decorator_args__: tuple[Any, ...] = ()

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        if len(args) == 3 and isinstance(args[1], tuple):
            superclass = args[1][-1].__class__
            if superclass is cls:
                return _make_subclass(args[0], superclass.__display_name__, superclass=superclass, attributes=args[2])
        return super().__new__(cls)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.__qualname__ = self.__name__

    def __len__(self) -> int:
        return 0

    def __contains__(self, key: str) -> bool:
        return False

    def __iter__(self) -> Iterator[Any]:
        return iter(())

    def __mro_entries__(self, bases: tuple[Any, ...]) -> tuple[type, ...]:
        return (self.__class__,)

    def __getitem__(self, key: Any) -> _MockObject:
        return _make_subclass(str(key), self.__display_name__, self.__class__)()

    def __getattr__(self, key: str) -> _MockObject:
        return _make_subclass(key, self.__display_name__, self.__class__)()

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        call = self.__class__()
        call.__sphinx_decorator_args__ = args
        return call

    def __repr__(self) -> str:
        return self.__display_name__

class _MockModule(ModuleType):
    """Used by autodoc_mock_imports."""
    __file__ = os.devnull
    __sphinx_mock__ = True

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.__all__: list[str] = []
        self.__path__: list[str] = []

    def __getattr__(self, name: str) -> _MockObject:
        return _make_subclass(name, self.__name__)()

    def __repr__(self) -> str:
        return self.__name__

class MockLoader(Loader):
    """A loader for mocking."""

    def __init__(self, finder: MockFinder) -> None:
        super().__init__()
        self.finder = finder

class MockFinder(MetaPathFinder):
    """A finder for mocking."""

    def __init__(self, modnames: list[str]) -> None:
        super().__init__()
        self.modnames = modnames
        self.loader = MockLoader(self)
        self.mocked_modules: list[str] = []

    def invalidate_caches(self) -> None:
        """Invalidate mocked modules on sys.modules."""
        for modname in self.mocked_modules:
            sys.modules.pop(modname, None)
        self.mocked_modules.clear()

@contextlib.contextmanager
def mock(modnames: list[str]) -> Iterator[None]:
    """Insert mock modules during context::

    with mock(['target.module.name']):
        # mock modules are enabled here
        ...
    """
    finder = MockFinder(modnames)
    sys.meta_path.insert(0, finder)
    try:
        yield
    finally:
        sys.meta_path.remove(finder)
        finder.invalidate_caches()

def ismockmodule(subject: Any) -> TypeIs[_MockModule]:
    """Check if the object is a mocked module."""
    return isinstance(subject, _MockModule)

def ismock(subject: Any) -> bool:
    """Check if the object is mocked."""
    return hasattr(subject, '__sphinx_mock__')

def undecorate(subject: _MockObject) -> Any:
    """Unwrap mock if *subject* is decorated by mocked object.

    If not decorated, returns given *subject* itself.
    """
    if ismock(subject) and subject.__sphinx_decorator_args__:
        return subject.__sphinx_decorator_args__[0]
    return subject
