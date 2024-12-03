"""Sphinx application class and extensibility interface.

Gracefully adapted from the TextPress system by Armin.
"""
from __future__ import annotations
import contextlib
import os
import pickle
import sys
from collections import deque
from io import StringIO
from os import path
from typing import TYPE_CHECKING, overload
from docutils.parsers.rst import Directive, roles
import sphinx
from sphinx import locale, package_dir
from sphinx.config import ENUM, Config, _ConfigRebuild
from sphinx.environment import BuildEnvironment
from sphinx.errors import ApplicationError, ConfigError, VersionRequirementError
from sphinx.events import EventManager
from sphinx.highlighting import lexer_classes
from sphinx.locale import __
from sphinx.project import Project
from sphinx.registry import SphinxComponentRegistry
from sphinx.util import docutils, logging
from sphinx.util._pathlib import _StrPath
from sphinx.util.build_phase import BuildPhase
from sphinx.util.console import bold
from sphinx.util.display import progress_message
from sphinx.util.i18n import CatalogRepository
from sphinx.util.logging import prefixed_warnings
from sphinx.util.osutil import ensuredir, relpath
from sphinx.util.tags import Tags
if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable, Sequence, Set
    from pathlib import Path
    from typing import IO, Any, Final, Literal
    from docutils import nodes
    from docutils.nodes import Element, Node
    from docutils.parsers import Parser
    from docutils.transforms import Transform
    from pygments.lexer import Lexer
    from sphinx import addnodes
    from sphinx.builders import Builder
    from sphinx.domains import Domain, Index
    from sphinx.environment.collectors import EnvironmentCollector
    from sphinx.ext.autodoc import Documenter
    from sphinx.ext.todo import todo_node
    from sphinx.extension import Extension
    from sphinx.roles import XRefRole
    from sphinx.search import SearchLanguage
    from sphinx.theming import Theme
    from sphinx.util.typing import RoleFunction, TitleGetter
builtin_extensions: tuple[str, ...] = ('sphinx.addnodes', 'sphinx.builders.changes', 'sphinx.builders.epub3', 'sphinx.builders.dirhtml', 'sphinx.builders.dummy', 'sphinx.builders.gettext', 'sphinx.builders.html', 'sphinx.builders.latex', 'sphinx.builders.linkcheck', 'sphinx.builders.manpage', 'sphinx.builders.singlehtml', 'sphinx.builders.texinfo', 'sphinx.builders.text', 'sphinx.builders.xml', 'sphinx.config', 'sphinx.domains.c', 'sphinx.domains.changeset', 'sphinx.domains.citation', 'sphinx.domains.cpp', 'sphinx.domains.index', 'sphinx.domains.javascript', 'sphinx.domains.math', 'sphinx.domains.python', 'sphinx.domains.rst', 'sphinx.domains.std', 'sphinx.directives', 'sphinx.directives.code', 'sphinx.directives.other', 'sphinx.directives.patches', 'sphinx.extension', 'sphinx.parsers', 'sphinx.registry', 'sphinx.roles', 'sphinx.transforms', 'sphinx.transforms.compact_bullet_list', 'sphinx.transforms.i18n', 'sphinx.transforms.references', 'sphinx.transforms.post_transforms', 'sphinx.transforms.post_transforms.code', 'sphinx.transforms.post_transforms.images', 'sphinx.versioning', 'sphinx.environment.collectors.dependencies', 'sphinx.environment.collectors.asset', 'sphinx.environment.collectors.metadata', 'sphinx.environment.collectors.title', 'sphinx.environment.collectors.toctree')
_first_party_extensions = ('sphinxcontrib.applehelp', 'sphinxcontrib.devhelp', 'sphinxcontrib.htmlhelp', 'sphinxcontrib.serializinghtml', 'sphinxcontrib.qthelp')
_first_party_themes = ('alabaster',)
builtin_extensions += _first_party_themes
builtin_extensions += _first_party_extensions
ENV_PICKLE_FILENAME = 'environment.pickle'
logger = logging.getLogger(__name__)

class Sphinx:
    """The main application class and extensibility interface.

    :ivar srcdir: Directory containing source.
    :ivar confdir: Directory containing ``conf.py``.
    :ivar doctreedir: Directory for storing pickled doctrees.
    :ivar outdir: Directory for storing build documents.
    """
    warningiserror: Final = False
    _warncount: int

    def __init__(self, srcdir: str | os.PathLike[str], confdir: str | os.PathLike[str] | None, outdir: str | os.PathLike[str], doctreedir: str | os.PathLike[str], buildername: str, confoverrides: dict | None=None, status: IO[str] | None=sys.stdout, warning: IO[str] | None=sys.stderr, freshenv: bool=False, warningiserror: bool=False, tags: Sequence[str]=(), verbosity: int=0, parallel: int=0, keep_going: bool=False, pdb: bool=False, exception_on_warning: bool=False) -> None:
        """Initialize the Sphinx application.

        :param srcdir: The path to the source directory.
        :param confdir: The path to the configuration directory.
            If not given, it is assumed to be the same as ``srcdir``.
        :param outdir: Directory for storing build documents.
        :param doctreedir: Directory for caching pickled doctrees.
        :param buildername: The name of the builder to use.
        :param confoverrides: A dictionary of configuration settings that override the
            settings in the configuration file.
        :param status: A file-like object to write status messages to.
        :param warning: A file-like object to write warnings to.
        :param freshenv: If true, clear the cached environment.
        :param warningiserror: If true, warnings become errors.
        :param tags: A list of tags to apply.
        :param verbosity: The verbosity level.
        :param parallel: The maximum number of parallel jobs to use
            when reading/writing documents.
        :param keep_going: Unused.
        :param pdb: If true, enable the Python debugger on an exception.
        :param exception_on_warning: If true, raise an exception on warnings.
        """
        self.phase = BuildPhase.INITIALIZATION
        self.verbosity = verbosity
        self._fresh_env_used: bool | None = None
        self.extensions: dict[str, Extension] = {}
        self.registry = SphinxComponentRegistry()
        self.srcdir = _StrPath(srcdir).resolve()
        self.outdir = _StrPath(outdir).resolve()
        self.doctreedir = _StrPath(doctreedir).resolve()
        if not path.isdir(self.srcdir):
            raise ApplicationError(__('Cannot find source directory (%s)') % self.srcdir)
        if path.exists(self.outdir) and (not path.isdir(self.outdir)):
            raise ApplicationError(__('Output directory (%s) is not a directory') % self.outdir)
        if self.srcdir == self.outdir:
            raise ApplicationError(__('Source directory and destination directory cannot be identical'))
        self.parallel = parallel
        if status is None:
            self._status: IO[str] = StringIO()
            self.quiet: bool = True
        else:
            self._status = status
            self.quiet = False
        if warning is None:
            self._warning: IO[str] = StringIO()
        else:
            self._warning = warning
        self._warncount = 0
        self.keep_going = bool(warningiserror)
        self._fail_on_warnings = bool(warningiserror)
        self.pdb = pdb
        self._exception_on_warning = exception_on_warning
        logging.setup(self, self._status, self._warning)
        self.events = EventManager(self)
        self.messagelog: deque = deque(maxlen=10)
        logger.info(bold(__('Running Sphinx v%s')), sphinx.__display_version__)
        self.statuscode = 0
        self.tags = Tags(tags)
        if confdir is None:
            self.confdir = self.srcdir
            self.config = Config({}, confoverrides or {})
        else:
            self.confdir = _StrPath(confdir).resolve()
            self.config = Config.read(self.confdir, confoverrides or {}, self.tags)
        self._init_i18n()
        if self.config.needs_sphinx and self.config.needs_sphinx > sphinx.__display_version__:
            raise VersionRequirementError(__('This project needs at least Sphinx v%s and therefore cannot be built with this version.') % self.config.needs_sphinx)
        for extension in builtin_extensions:
            self.setup_extension(extension)
        for extension in self.config.extensions:
            self.setup_extension(extension)
        self.preload_builder(buildername)
        if not path.isdir(outdir):
            with progress_message(__('making output directory')):
                ensuredir(outdir)
        if self.config.setup:
            prefix = __('while setting up extension %s:') % 'conf.py'
            with prefixed_warnings(prefix):
                if callable(self.config.setup):
                    self.config.setup(self)
                else:
                    raise ConfigError(__("'setup' as currently defined in conf.py isn't a Python callable. Please modify its definition to make it a callable function. This is needed for conf.py to behave as a Sphinx extension."))
        self.config._report_override_warnings()
        self.events.emit('config-inited', self.config)
        self.project = Project(self.srcdir, self.config.source_suffix)
        self.env = self._init_env(freshenv)
        self.builder = self.create_builder(buildername)
        self._post_init_env()
        self._init_builder()

    @property
    def fresh_env_used(self) -> bool | None:
        """True/False as to whether a new environment was created for this build,
        or None if the environment has not been initialised yet.
        """
        return self._fresh_env_used

    def _init_i18n(self) -> None:
        """Load translated strings from the configured localedirs if enabled in
        the configuration.
        """
        locale.setlocale(locale.LC_ALL, '')
        locale.textdomain('sphinx')
        locale_dirs = [path.join(package_dir, 'locale')] + self.config.locale_dirs
        self.translator, has_translation = locale.init(locale_dirs, self.config.language)
        if self.config.language and not has_translation:
            logger.warning(__('No translation found for language %s'), self.config.language)

    def setup_extension(self, extname: str) -> None:
        """Import and setup a Sphinx extension module.

        Load the extension given by the module *name*.  Use this if your
        extension needs the features provided by another extension.  No-op if
        called twice.
        """
        if extname in self.extensions:
            return
        try:
            mod = __import__(extname, None, None, ['setup'])
        except ImportError as err:
            logger.warning(__('Failed to import extension %s'), extname)
            logger.warning(__('The error was: %s'), err)
            return
        if not hasattr(mod, 'setup'):
            logger.warning(__('Extension %s has no setup() function; is it really a Sphinx extension module?'), extname)
            return
        if extname in self.extensions:
            logger.warning(__('Extension %s already loaded; ignoring subsequent import'), extname)
            return
        try:
            mod.setup(self)
        except Exception as err:
            logger.warning(__('Failed to setup extension %s'), extname)
            logger.warning(__('The error was: %s'), err)
        else:
            self.extensions[extname] = mod

    @staticmethod
    def require_sphinx(version: tuple[int, int] | str) -> None:
        """Check the Sphinx version if requested.

        Compare *version* with the version of the running Sphinx, and abort the
        build when it is too old.

        :param version: The required version in the form of ``major.minor`` or
                        ``(major, minor)``.

        .. versionadded:: 1.0
        .. versionchanged:: 7.1
           Type of *version* now allows ``(major, minor)`` form.
        """
        if isinstance(version, str):
            version = tuple(int(x) for x in version.split('.'))
        elif not isinstance(version, tuple):
            raise TypeError('version must be a string or tuple')
        
        if version > sphinx.__version_info__[:2]:
            raise VersionRequirementError(
                __('This project needs at least Sphinx v%s and therefore cannot '
                   'be built with this version.') % '.'.join(map(str, version)))

    def connect(self, event: str, callback: Callable, priority: int=500) -> int:
        """Register *callback* to be called when *event* is emitted.

        For details on available core events and the arguments of callback
        functions, please see :ref:`events`.

        :param event: The name of target event
        :param callback: Callback function for the event
        :param priority: The priority of the callback.  The callbacks will be invoked
                         in order of *priority* (ascending).
        :return: A listener ID.  It can be used for :meth:`disconnect`.

        .. versionchanged:: 3.0

           Support *priority*
        """
        pass

    def disconnect(self, listener_id: int) -> None:
        """Unregister callback by *listener_id*.

        :param listener_id: A listener_id that :meth:`connect` returns
        """
        pass

    def emit(self, event: str, *args: Any, allowed_exceptions: tuple[type[Exception], ...]=()) -> list:
        """Emit *event* and pass *arguments* to the callback functions.

        Return the return values of all callbacks as a list.  Do not emit core
        Sphinx events in extensions!

        :param event: The name of event that will be emitted
        :param args: The arguments for the event
        :param allowed_exceptions: The list of exceptions that are allowed in the callbacks

        .. versionchanged:: 3.1

           Added *allowed_exceptions* to specify path-through exceptions
        """
        pass

    def emit_firstresult(self, event: str, *args: Any, allowed_exceptions: tuple[type[Exception], ...]=()) -> Any:
        """Emit *event* and pass *arguments* to the callback functions.

        Return the result of the first callback that doesn't return ``None``.

        :param event: The name of event that will be emitted
        :param args: The arguments for the event
        :param allowed_exceptions: The list of exceptions that are allowed in the callbacks

        .. versionadded:: 0.5
        .. versionchanged:: 3.1

           Added *allowed_exceptions* to specify path-through exceptions
        """
        pass

    def add_builder(self, builder: type[Builder], override: bool=False) -> None:
        """Register a new builder.

        :param builder: A builder class
        :param override: If true, install the builder forcedly even if another builder
                         is already installed as the same name

        .. versionchanged:: 1.8
           Add *override* keyword.
        """
        pass

    def add_config_value(self, name: str, default: Any, rebuild: _ConfigRebuild, types: type | Collection[type] | ENUM=(), description: str='') -> None:
        """Register a configuration value.

        This is necessary for Sphinx to recognize new values and set default
        values accordingly.


        :param name: The name of the configuration value.  It is recommended to be prefixed
                     with the extension name (ex. ``html_logo``, ``epub_title``)
        :param default: The default value of the configuration.
        :param rebuild: The condition of rebuild.  It must be one of those values:

                        * ``'env'`` if a change in the setting only takes effect when a
                          document is parsed -- this means that the whole environment must be
                          rebuilt.
                        * ``'html'`` if a change in the setting needs a full rebuild of HTML
                          documents.
                        * ``''`` if a change in the setting will not need any special rebuild.
        :param types: The type of configuration value.  A list of types can be specified.  For
                      example, ``[str]`` is used to describe a configuration that takes string
                      value.
        :param description: A short description of the configuration value.

        .. versionchanged:: 0.4
           If the *default* value is a callable, it will be called with the
           config object as its argument in order to get the default value.
           This can be used to implement config values whose default depends on
           other values.

        .. versionchanged:: 0.6
           Changed *rebuild* from a simple boolean (equivalent to ``''`` or
           ``'env'``) to a string.  However, booleans are still accepted and
           converted internally.

        .. versionadded:: 7.4
           The *description* parameter.
        """
        pass

    def add_event(self, name: str) -> None:
        """Register an event called *name*.

        This is needed to be able to emit it.

        :param name: The name of the event
        """
        pass

    def set_translator(self, name: str, translator_class: type[nodes.NodeVisitor], override: bool=False) -> None:
        """Register or override a Docutils translator class.

        This is used to register a custom output translator or to replace a
        builtin translator.  This allows extensions to use a custom translator
        and define custom nodes for the translator (see :meth:`add_node`).

        :param name: The name of the builder for the translator
        :param translator_class: A translator class
        :param override: If true, install the translator forcedly even if another translator
                         is already installed as the same name

        .. versionadded:: 1.3
        .. versionchanged:: 1.8
           Add *override* keyword.
        """
        pass

    def add_node(self, node: type[Element], override: bool=False, **kwargs: tuple[Callable, Callable | None]) -> None:
        """Register a Docutils node class.

        This is necessary for Docutils internals.  It may also be used in the
        future to validate nodes in the parsed documents.

        :param node: A node class
        :param kwargs: Visitor functions for each builder (see below)
        :param override: If true, install the node forcedly even if another node is already
                         installed as the same name

        Node visitor functions for the Sphinx HTML, LaTeX, text and manpage
        writers can be given as keyword arguments: the keyword should be one or
        more of ``'html'``, ``'latex'``, ``'text'``, ``'man'``, ``'texinfo'``
        or any other supported translators, the value a 2-tuple of ``(visit,
        depart)`` methods.  ``depart`` can be ``None`` if the ``visit``
        function raises :exc:`docutils.nodes.SkipNode`.  Example:

        .. code-block:: python

           class math(docutils.nodes.Element): pass

           def visit_math_html(self, node):
               self.body.append(self.starttag(node, 'math'))
           def depart_math_html(self, node):
               self.body.append('</math>')

           app.add_node(math, html=(visit_math_html, depart_math_html))

        Obviously, translators for which you don't specify visitor methods will
        choke on the node when encountered in a document to translate.

        .. versionchanged:: 0.5
           Added the support for keyword arguments giving visit functions.
        """
        pass

    def add_enumerable_node(self, node: type[Element], figtype: str, title_getter: TitleGetter | None=None, override: bool=False, **kwargs: tuple[Callable, Callable]) -> None:
        """Register a Docutils node class as a numfig target.

        Sphinx numbers the node automatically. And then the users can refer it
        using :rst:role:`numref`.

        :param node: A node class
        :param figtype: The type of enumerable nodes.  Each figtype has individual numbering
                        sequences.  As system figtypes, ``figure``, ``table`` and
                        ``code-block`` are defined.  It is possible to add custom nodes to
                        these default figtypes.  It is also possible to define new custom
                        figtype if a new figtype is given.
        :param title_getter: A getter function to obtain the title of node.  It takes an
                             instance of the enumerable node, and it must return its title as
                             string.  The title is used to the default title of references for
                             :rst:role:`ref`.  By default, Sphinx searches
                             ``docutils.nodes.caption`` or ``docutils.nodes.title`` from the
                             node as a title.
        :param kwargs: Visitor functions for each builder (same as :meth:`add_node`)
        :param override: If true, install the node forcedly even if another node is already
                         installed as the same name

        .. versionadded:: 1.4
        """
        pass

    def add_directive(self, name: str, cls: type[Directive], override: bool=False) -> None:
        """Register a Docutils directive.

        :param name: The name of the directive
        :param cls: A directive class
        :param override: If false, do not install it if another directive
                         is already installed as the same name
                         If true, unconditionally install the directive.

        For example, a custom directive named ``my-directive`` would be added
        like this:

        .. code-block:: python

           from docutils.parsers.rst import Directive, directives

           class MyDirective(Directive):
               has_content = True
               required_arguments = 1
               optional_arguments = 0
               final_argument_whitespace = True
               option_spec = {
                   'class': directives.class_option,
                   'name': directives.unchanged,
               }

               def run(self):
                   ...

           def setup(app):
               app.add_directive('my-directive', MyDirective)

        For more details, see `the Docutils docs
        <https://docutils.sourceforge.io/docs/howto/rst-directives.html>`__ .

        .. versionchanged:: 0.6
           Docutils 0.5-style directive classes are now supported.
        .. deprecated:: 1.8
           Docutils 0.4-style (function based) directives support is deprecated.
        .. versionchanged:: 1.8
           Add *override* keyword.
        """
        pass

    def add_role(self, name: str, role: Any, override: bool=False) -> None:
        """Register a Docutils role.

        :param name: The name of role
        :param role: A role function
        :param override: If false, do not install it if another role
                         is already installed as the same name
                         If true, unconditionally install the role.

        For more details about role functions, see `the Docutils docs
        <https://docutils.sourceforge.io/docs/howto/rst-roles.html>`__ .

        .. versionchanged:: 1.8
           Add *override* keyword.
        """
        pass

    def add_generic_role(self, name: str, nodeclass: type[Node], override: bool=False) -> None:
        """Register a generic Docutils role.

        Register a Docutils role that does nothing but wrap its contents in the
        node given by *nodeclass*.

        :param override: If false, do not install it if another role
                         is already installed as the same name
                         If true, unconditionally install the role.

        .. versionadded:: 0.6
        .. versionchanged:: 1.8
           Add *override* keyword.
        """
        pass

    def add_domain(self, domain: type[Domain], override: bool=False) -> None:
        """Register a domain.

        :param domain: A domain class
        :param override: If false, do not install it if another domain
                         is already installed as the same name
                         If true, unconditionally install the domain.

        .. versionadded:: 1.0
        .. versionchanged:: 1.8
           Add *override* keyword.
        """
        pass

    def add_directive_to_domain(self, domain: str, name: str, cls: type[Directive], override: bool=False) -> None:
        """Register a Docutils directive in a domain.

        Like :meth:`add_directive`, but the directive is added to the domain
        named *domain*.

        :param domain: The name of target domain
        :param name: A name of directive
        :param cls: A directive class
        :param override: If false, do not install it if another directive
                         is already installed as the same name
                         If true, unconditionally install the directive.

        .. versionadded:: 1.0
        .. versionchanged:: 1.8
           Add *override* keyword.
        """
        pass

    def add_role_to_domain(self, domain: str, name: str, role: RoleFunction | XRefRole, override: bool=False) -> None:
        """Register a Docutils role in a domain.

        Like :meth:`add_role`, but the role is added to the domain named
        *domain*.

        :param domain: The name of the target domain
        :param name: The name of the role
        :param role: The role function
        :param override: If false, do not install it if another role
                         is already installed as the same name
                         If true, unconditionally install the role.

        .. versionadded:: 1.0
        .. versionchanged:: 1.8
           Add *override* keyword.
        """
        pass

    def add_index_to_domain(self, domain: str, index: type[Index], _override: bool=False) -> None:
        """Register a custom index for a domain.

        Add a custom *index* class to the domain named *domain*.

        :param domain: The name of the target domain
        :param index: The index class
        :param override: If false, do not install it if another index
                         is already installed as the same name
                         If true, unconditionally install the index.

        .. versionadded:: 1.0
        .. versionchanged:: 1.8
           Add *override* keyword.
        """
        pass

    def add_object_type(self, directivename: str, rolename: str, indextemplate: str='', parse_node: Callable | None=None, ref_nodeclass: type[nodes.TextElement] | None=None, objname: str='', doc_field_types: Sequence=(), override: bool=False) -> None:
        """Register a new object type.

        This method is a very convenient way to add a new :term:`object` type
        that can be cross-referenced.  It will do this:

        - Create a new directive (called *directivename*) for documenting an
          object.  It will automatically add index entries if *indextemplate*
          is nonempty; if given, it must contain exactly one instance of
          ``%s``.  See the example below for how the template will be
          interpreted.
        - Create a new role (called *rolename*) to cross-reference to these
          object descriptions.
        - If you provide *parse_node*, it must be a function that takes a
          string and a docutils node, and it must populate the node with
          children parsed from the string.  It must then return the name of the
          item to be used in cross-referencing and index entries.  See the
          :file:`conf.py` file in the source for this documentation for an
          example.
        - The *objname* (if not given, will default to *directivename*) names
          the type of object.  It is used when listing objects, e.g. in search
          results.

        For example, if you have this call in a custom Sphinx extension::

           app.add_object_type('directive', 'dir', 'pair: %s; directive')

        you can use this markup in your documents::

           .. rst:directive:: function

              Document a function.

           <...>

           See also the :rst:dir:`function` directive.

        For the directive, an index entry will be generated as if you had prepended ::

           .. index:: pair: function; directive

        The reference node will be of class ``literal`` (so it will be rendered
        in a proportional font, as appropriate for code) unless you give the
        *ref_nodeclass* argument, which must be a docutils node class.  Most
        useful are ``docutils.nodes.emphasis`` or ``docutils.nodes.strong`` --
        you can also use ``docutils.nodes.generated`` if you want no further
        text decoration.  If the text should be treated as literal (e.g. no
        smart quote replacement), but not have typewriter styling, use
        ``sphinx.addnodes.literal_emphasis`` or
        ``sphinx.addnodes.literal_strong``.

        For the role content, you have the same syntactical possibilities as
        for standard Sphinx roles (see :ref:`xref-syntax`).

        If *override* is True, the given object_type is forcedly installed even if
        an object_type having the same name is already installed.

        .. versionchanged:: 1.8
           Add *override* keyword.
        """
        pass

    def add_crossref_type(self, directivename: str, rolename: str, indextemplate: str='', ref_nodeclass: type[nodes.TextElement] | None=None, objname: str='', override: bool=False) -> None:
        """Register a new crossref object type.

        This method is very similar to :meth:`~Sphinx.add_object_type` except that the
        directive it generates must be empty, and will produce no output.

        That means that you can add semantic targets to your sources, and refer
        to them using custom roles instead of generic ones (like
        :rst:role:`ref`).  Example call::

           app.add_crossref_type('topic', 'topic', 'single: %s',
                                 docutils.nodes.emphasis)

        Example usage::

           .. topic:: application API

           The application API
           -------------------

           Some random text here.

           See also :topic:`this section <application API>`.

        (Of course, the element following the ``topic`` directive needn't be a
        section.)


        :param override: If false, do not install it if another cross-reference type
                         is already installed as the same name
                         If true, unconditionally install the cross-reference type.

        .. versionchanged:: 1.8
           Add *override* keyword.
        """
        pass

    def add_transform(self, transform: type[Transform]) -> None:
        """Register a Docutils transform to be applied after parsing.

        Add the standard docutils :class:`~docutils.transforms.Transform`
        subclass *transform* to the list of transforms that are applied after
        Sphinx parses a reST document.

        :param transform: A transform class

        .. list-table:: priority range categories for Sphinx transforms
           :widths: 20,80

           * - Priority
             - Main purpose in Sphinx
           * - 0-99
             - Fix invalid nodes by docutils. Translate a doctree.
           * - 100-299
             - Preparation
           * - 300-399
             - early
           * - 400-699
             - main
           * - 700-799
             - Post processing. Deadline to modify text and referencing.
           * - 800-899
             - Collect referencing and referenced nodes. Domain processing.
           * - 900-999
             - Finalize and clean up.

        refs: `Transform Priority Range Categories`__

        __ https://docutils.sourceforge.io/docs/ref/transforms.html#transform-priority-range-categories
        """
        pass

    def add_post_transform(self, transform: type[Transform]) -> None:
        """Register a Docutils transform to be applied before writing.

        Add the standard docutils :class:`~docutils.transforms.Transform`
        subclass *transform* to the list of transforms that are applied before
        Sphinx writes a document.

        :param transform: A transform class
        """
        pass

    def add_js_file(self, filename: str | None, priority: int=500, loading_method: str | None=None, **kwargs: Any) -> None:
        """Register a JavaScript file to include in the HTML output.

        :param filename: The name of a JavaScript file that the default HTML
                         template will include. It must be relative to the HTML
                         static path, or a full URI with scheme, or ``None`` .
                         The ``None`` value is used to create an inline
                         ``<script>`` tag.  See the description of *kwargs*
                         below.
        :param priority: Files are included in ascending order of priority. If
                         multiple JavaScript files have the same priority,
                         those files will be included in order of registration.
                         See list of "priority range for JavaScript files" below.
        :param loading_method: The loading method for the JavaScript file.
                               Either ``'async'`` or ``'defer'`` are allowed.
        :param kwargs: Extra keyword arguments are included as attributes of the
                       ``<script>`` tag.  If the special keyword argument
                       ``body`` is given, its value will be added as the content
                       of the  ``<script>`` tag.

        Example::

            app.add_js_file('example.js')
            # => <script src="_static/example.js"></script>

            app.add_js_file('example.js', loading_method="async")
            # => <script src="_static/example.js" async="async"></script>

            app.add_js_file(None, body="var myVariable = 'foo';")
            # => <script>var myVariable = 'foo';</script>

        .. list-table:: priority range for JavaScript files
           :widths: 20,80

           * - Priority
             - Main purpose in Sphinx
           * - 200
             - default priority for built-in JavaScript files
           * - 500
             - default priority for extensions
           * - 800
             - default priority for :confval:`html_js_files`

        A JavaScript file can be added to the specific HTML page when an extension
        calls this method on :event:`html-page-context` event.

        .. versionadded:: 0.5

        .. versionchanged:: 1.8
           Renamed from ``app.add_javascript()``.
           And it allows keyword arguments as attributes of script tag.

        .. versionchanged:: 3.5
           Take priority argument.  Allow to add a JavaScript file to the specific page.
        .. versionchanged:: 4.4
           Take loading_method argument.  Allow to change the loading method of the
           JavaScript file.
        """
        pass

    def add_css_file(self, filename: str, priority: int=500, **kwargs: Any) -> None:
        """Register a stylesheet to include in the HTML output.

        :param filename: The name of a CSS file that the default HTML
                         template will include. It must be relative to the HTML
                         static path, or a full URI with scheme.
        :param priority: Files are included in ascending order of priority. If
                         multiple CSS files have the same priority,
                         those files will be included in order of registration.
                         See list of "priority range for CSS files" below.
        :param kwargs: Extra keyword arguments are included as attributes of the
                       ``<link>`` tag.

        Example::

            app.add_css_file('custom.css')
            # => <link rel="stylesheet" href="_static/custom.css" type="text/css" />

            app.add_css_file('print.css', media='print')
            # => <link rel="stylesheet" href="_static/print.css"
            #          type="text/css" media="print" />

            app.add_css_file('fancy.css', rel='alternate stylesheet', title='fancy')
            # => <link rel="alternate stylesheet" href="_static/fancy.css"
            #          type="text/css" title="fancy" />

        .. list-table:: priority range for CSS files
           :widths: 20,80

           * - Priority
             - Main purpose in Sphinx
           * - 200
             - default priority for built-in CSS files
           * - 500
             - default priority for extensions
           * - 800
             - default priority for :confval:`html_css_files`

        A CSS file can be added to the specific HTML page when an extension calls
        this method on :event:`html-page-context` event.

        .. versionadded:: 1.0

        .. versionchanged:: 1.6
           Optional ``alternate`` and/or ``title`` attributes can be supplied
           with the arguments *alternate* (a Boolean) and *title* (a string).
           The default is no title and *alternate* = ``False``. For
           more information, refer to the `documentation
           <https://mdn.io/Web/CSS/Alternative_style_sheets>`__.

        .. versionchanged:: 1.8
           Renamed from ``app.add_stylesheet()``.
           And it allows keyword arguments as attributes of link tag.

        .. versionchanged:: 3.5
           Take priority argument.  Allow to add a CSS file to the specific page.
        """
        pass

    def add_latex_package(self, packagename: str, options: str | None=None, after_hyperref: bool=False) -> None:
        """Register a package to include in the LaTeX source code.

        Add *packagename* to the list of packages that LaTeX source code will
        include.  If you provide *options*, it will be taken to the `\\usepackage`
        declaration.  If you set *after_hyperref* truthy, the package will be
        loaded after ``hyperref`` package.

        .. code-block:: python

           app.add_latex_package('mypackage')
           # => \\usepackage{mypackage}
           app.add_latex_package('mypackage', 'foo,bar')
           # => \\usepackage[foo,bar]{mypackage}

        .. versionadded:: 1.3
        .. versionadded:: 3.1

           *after_hyperref* option.
        """
        pass

    def add_lexer(self, alias: str, lexer: type[Lexer]) -> None:
        """Register a new lexer for source code.

        Use *lexer* to highlight code blocks with the given language *alias*.

        .. versionadded:: 0.6
        .. versionchanged:: 2.1
           Take a lexer class as an argument.
        .. versionchanged:: 4.0
           Removed support for lexer instances as an argument.
        """
        pass

    def add_autodocumenter(self, cls: type[Documenter], override: bool=False) -> None:
        """Register a new documenter class for the autodoc extension.

        Add *cls* as a new documenter class for the :mod:`sphinx.ext.autodoc`
        extension.  It must be a subclass of
        :class:`sphinx.ext.autodoc.Documenter`.  This allows auto-documenting
        new types of objects.  See the source of the autodoc module for
        examples on how to subclass :class:`~sphinx.ext.autodoc.Documenter`.

        If *override* is True, the given *cls* is forcedly installed even if
        a documenter having the same name is already installed.

        See :ref:`autodoc_ext_tutorial`.

        .. versionadded:: 0.6
        .. versionchanged:: 2.2
           Add *override* keyword.
        """
        pass

    def add_autodoc_attrgetter(self, typ: type, getter: Callable[[Any, str, Any], Any]) -> None:
        """Register a new ``getattr``-like function for the autodoc extension.

        Add *getter*, which must be a function with an interface compatible to
        the :func:`getattr` builtin, as the autodoc attribute getter for
        objects that are instances of *typ*.  All cases where autodoc needs to
        get an attribute of a type are then handled by this function instead of
        :func:`getattr`.

        .. versionadded:: 0.6
        """
        pass

    def add_search_language(self, cls: type[SearchLanguage]) -> None:
        """Register a new language for the HTML search index.

        Add *cls*, which must be a subclass of
        :class:`sphinx.search.SearchLanguage`, as a support language for
        building the HTML full-text search index.  The class must have a *lang*
        attribute that indicates the language it should be used for.  See
        :confval:`html_search_language`.

        .. versionadded:: 1.1
        """
        pass

    def add_source_suffix(self, suffix: str, filetype: str, override: bool=False) -> None:
        """Register a suffix of source files.

        Same as :confval:`source_suffix`.  The users can override this
        using the config setting.

        :param override: If false, do not install it the same suffix
                         is already installed.
                         If true, unconditionally install the suffix.

        .. versionadded:: 1.8
        """
        pass

    def add_source_parser(self, parser: type[Parser], override: bool=False) -> None:
        """Register a parser class.

        :param override: If false, do not install it if another parser
                         is already installed for the same suffix.
                         If true, unconditionally install the parser.

        .. versionadded:: 1.4
        .. versionchanged:: 1.8
           *suffix* argument is deprecated.  It only accepts *parser* argument.
           Use :meth:`add_source_suffix` API to register suffix instead.
        .. versionchanged:: 1.8
           Add *override* keyword.
        """
        pass

    def add_env_collector(self, collector: type[EnvironmentCollector]) -> None:
        """Register an environment collector class.

        Refer to :ref:`collector-api`.

        .. versionadded:: 1.6
        """
        pass

    def add_html_theme(self, name: str, theme_path: str) -> None:
        """Register a HTML Theme.

        The *name* is a name of theme, and *theme_path* is a full path to the
        theme (refs: :ref:`distribute-your-theme`).

        .. versionadded:: 1.6
        """
        pass

    def add_html_math_renderer(self, name: str, inline_renderers: tuple[Callable, Callable | None] | None=None, block_renderers: tuple[Callable, Callable | None] | None=None) -> None:
        """Register a math renderer for HTML.

        The *name* is a name of math renderer.  Both *inline_renderers* and
        *block_renderers* are used as visitor functions for the HTML writer:
        the former for inline math node (``nodes.math``), the latter for
        block math node (``nodes.math_block``).  Regarding visitor functions,
        see :meth:`add_node` for details.

        .. versionadded:: 1.8

        """
        pass

    def add_message_catalog(self, catalog: str, locale_dir: str) -> None:
        """Register a message catalog.

        :param catalog: The name of the catalog
        :param locale_dir: The base path of the message catalog

        For more details, see :func:`sphinx.locale.get_translation()`.

        .. versionadded:: 1.8
        """
        pass

    def is_parallel_allowed(self, typ: str) -> bool:
        """Check whether parallel processing is allowed or not.

        :param typ: A type of processing; ``'read'`` or ``'write'``.
        """
        pass

    def set_html_assets_policy(self, policy: Literal['always', 'per_page']) -> None:
        """Set the policy to include assets in HTML pages.

        - always: include the assets in all the pages
        - per_page: include the assets only in pages where they are used

        .. versionadded: 4.1
        """
        pass

class TemplateBridge:
    """
    This class defines the interface for a "template bridge", that is, a class
    that renders templates given a template name and a context.
    """

    def init(self, builder: Builder, theme: Theme | None=None, dirs: list[str] | None=None) -> None:
        """Called by the builder to initialize the template system.

        *builder* is the builder object; you'll probably want to look at the
        value of ``builder.config.templates_path``.

        *theme* is a :class:`sphinx.theming.Theme` object or None; in the latter
        case, *dirs* can be list of fixed directories to look for templates.
        """
        pass

    def newest_template_mtime(self) -> float:
        """Called by the builder to determine if output files are outdated
        because of template changes.  Return the mtime of the newest template
        file that was changed.  The default implementation returns ``0``.
        """
        pass

    def render(self, template: str, context: dict) -> None:
        """Called by the builder to render a template given as a filename with
        a specified context (a Python dictionary).
        """
        pass

    def render_string(self, template: str, context: dict) -> str:
        """Called by the builder to render a template given as a string with a
        specified context (a Python dictionary).
        """
        pass
